from unittest.mock import Mock, patch
import pytest
from companion import whatsapp_web as web
from companion.policy import AttentionRequired, PolicyError


@pytest.mark.parametrize('url',[
    'https://evil.test/', 'https://whatsapp.com.evil.test/',
    'http://web.whatsapp.com/', 'wss://user:secret@web.whatsapp.com/',
    'https://web.whatsapp.com:8000/', 'https://127.0.0.1/',
])
def test_network_rejects_unapproved_schemes_and_destinations(url):
    with patch.object(web,'DomainPolicy') as policy,pytest.raises(PolicyError):
        web.network_url(url)
    policy.assert_not_called()


@pytest.mark.parametrize('url',['https://web.whatsapp.com/','wss://web.whatsapp.com/ws','wss://web.whatsapp.com:5222/ws','https://static.whatsapp.net/a'])
def test_whatsapp_connections_still_require_public_dns(url):
    with patch.object(web,'DomainPolicy') as policy:
        web.network_url(url)
    assert policy.call_args.args[0] in (['web.whatsapp.com'],['static.whatsapp.net'])
    assert policy.return_value.check.call_args.args[0].startswith('https://')
    with patch.object(web,'DomainPolicy') as policy:
        policy.return_value.check.side_effect=PolicyError('Private address')
        with pytest.raises(PolicyError):web.network_url(url)


def test_setup_uses_only_the_isolated_profile_and_fixed_home(tmp_path):
    with patch.object(web,'profile_busy',return_value=False), \
         patch.object(web,'_installed_browser',return_value='brave.exe'),patch('subprocess.Popen') as launched:
        web.open_login(tmp_path/'whatsapp-brave-profile')
    args=launched.call_args.args[0]
    assert args[-1]==web.HOME
    assert '--user-data-dir='+str(tmp_path/'whatsapp-brave-profile') in args
    assert launched.call_args.kwargs['shell'] is False


def test_busy_profile_is_not_relaunched_or_killed(tmp_path):
    with patch.object(web,'profile_busy',return_value=True),patch('subprocess.Popen') as launched:
        assert web.open_login(tmp_path)['already_open']
    launched.assert_not_called()


# Real DOM fixture; every request is fulfilled locally. It cannot reach or send
# to a WhatsApp account. This validates selectors, typing and receipt identity.
HTML='''<html><body><div id="side"><div contenteditable="true" role="textbox"></div></div>
<div id="pane-side"><div data-testid="cell-frame-container"><div data-testid="cell-frame-title"><span title="MSV Krishna" onclick="document.querySelector('header').textContent='MSV Krishna'">MSV Krishna</span></div></div></div>
<div id="main"><header>Other chat</header><div id="messages"></div>
<footer><div contenteditable="true" role="textbox"></div></footer></div>
<script>let counter=0; document.querySelector('footer div').addEventListener('keydown',e=>{
if(e.key==='Enter'){e.preventDefault();let text=e.target.innerText;e.target.textContent='';
if(document.body.dataset.noReceipt)return;
let row=document.createElement('div');row.dataset.id='new-'+(++counter);
row.innerHTML='<div class="message-out"><div data-pre-plain-text="time"><span class="selectable-text"></span></div></div>';
row.querySelector('span').textContent=text;document.querySelector('#messages').appendChild(row);}});</script></body></html>'''


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        try:
            executable=web._installed_browser('brave')
        except RuntimeError:
            pytest.skip('Optional real DOM fixture needs installed Brave.')
        browser=playwright.chromium.launch(executable_path=executable,headless=True)
        context=browser.new_context()
        context.route('**/*',lambda route:route.fulfill(status=200,body=HTML,content_type='text/html'))
        page=context.new_page()
        page.goto(web.HOME)
        try:yield page
        finally:browser.close()


def send(page,**options):
    with patch.object(page,'wait_for_timeout'):
        return web.send_on_page(page,{'recipient':'MSV Krishna','message':'Hello Krishna'},
            before_mutation=options.pop('before',Mock()),check=options.pop('check',lambda:None),**options)


def test_real_dom_send_requires_a_new_outgoing_id(page):
    result=send(page)
    assert result['outgoing_verified'] and not result['delivery_verified']
    assert web.outgoing(page,'Hello Krishna')=={'new-1'}
    assert page.locator(web.COMPOSER).inner_text()==''


def test_current_tail_marker_and_opaque_id_are_outgoing_evidence(page):
    send(page)
    page.locator('.message-out').evaluate('(el)=>{el.className="";let tail=document.createElement("span");tail.dataset.icon="tail-out";el.appendChild(tail)}')
    assert web.outgoing(page,'Hello Krishna')=={'new-1'}
    page.locator('[data-icon="tail-out"]').evaluate('(el)=>el.dataset.icon="tail-in"')
    assert not web.outgoing(page,'Hello Krishna')


def test_message_search_hits_do_not_become_duplicate_contacts(page):
    page.locator('#pane-side').evaluate('(el)=>{let hit=document.createElement("div");hit.dataset.testid="chatlist-message-fixture";let name=document.createElement("span");name.title="MSV Krishna";name.textContent="MSV Krishna";hit.appendChild(name);el.appendChild(hit)}')
    assert send(page)['outgoing_verified']


def test_existing_draft_is_not_overwritten(page):
    page.locator(web.COMPOSER).fill('Existing draft')
    with pytest.raises(AttentionRequired,match='draft'):send(page)
    assert page.locator(web.COMPOSER).inner_text()=='Existing draft'
    assert not web.outgoing(page,'Hello Krishna')


def test_duplicate_recipient_stops_before_message_typing(page):
    page.locator('#pane-side').evaluate('(el)=>el.appendChild(el.firstElementChild.cloneNode(true))')
    with pytest.raises(AttentionRequired,match='unique exact'):send(page)
    assert page.locator(web.COMPOSER).inner_text()==''


def test_changed_header_after_typing_preserves_unsent_draft(page):
    def progress(stage):
        if stage=='verifying':page.locator('#main header').evaluate('(el)=>el.textContent="Wrong chat"')
    with pytest.raises(AttentionRequired,match='header'):send(page,progress=progress)
    assert page.locator(web.COMPOSER).inner_text()=='Hello Krishna'
    assert not web.outgoing(page,'Hello Krishna')


def test_old_matching_bubble_cannot_certify_new_send(page):
    send(page)
    page.locator('body').evaluate('(el)=>el.dataset.noReceipt="true"')
    with pytest.raises(AttentionRequired,match='uncertain'):send(page)
    assert web.outgoing(page,'Hello Krishna')=={'new-1'}


def test_paused_before_send_keeps_draft_unsent(page):
    stopped=[False]
    def progress(stage):
        if stage=='verifying':stopped[0]=True
    def check():
        if stopped[0]:raise AttentionRequired('Paused')
    with pytest.raises(AttentionRequired,match='Paused'):send(page,check=check,progress=progress)
    assert not web.outgoing(page,'Hello Krishna')


def test_web_worker_dispatch_is_journaled_and_cached_without_native_input(tmp_path):
    from types import SimpleNamespace
    from companion.runner import Worker
    from companion.client import ClientError
    from companion.journal import Journal
    journal=Journal(tmp_path/'jobs.sqlite3')
    client=Mock()
    client.progress.side_effect=ClientError('Unavailable')
    worker=Worker(SimpleNamespace(state_dir=tmp_path,whatsapp_profile=tmp_path/'whatsapp-brave-profile'),client,journal=journal)
    job={'id':'web-fixture','tool':'desktop.whatsapp',
         'args':{'recipient':'MSV Krishna','message':'Hello','transport':'brave_web'},
         'policy':{'allowed_tools':['desktop.whatsapp']}}
    def execute(args,*,before_mutation,progress,**kwargs):
        before_mutation(0)
        progress('checking')
        return {'outgoing_verified':True,'next_action':1}
    try:
        with patch.object(web,'send_web',side_effect=execute) as sender,patch('companion.whatsapp.send_current') as native:
            assert worker.execute(job)['status']=='completed'
            assert worker.execute(job)['status']=='completed'
        assert sender.call_count==1
        native.assert_not_called()
        assert not journal.state(job['id'])[1]
    finally:journal.close()


def test_grouped_bubbles_use_calibrated_edges_and_reject_incoming(page):
    page.locator('#messages').evaluate("""el => {
      for (const [id, direction, width, tail] of [
        ['out','out',200,true], ['in','in',100,true],
        ['grouped','out',130,false], ['incoming','in',180,false]]) {
        const row=document.createElement('div');row.dataset.id=id;
        row.style.cssText='width:600px;display:flex;justify-content:'+(direction==='out'?'flex-end':'flex-start');
        row.innerHTML='<div data-testid="msg-container" style="width:'+width+'px">'+
          (tail?'<span data-icon="tail-'+direction+'"></span>':'')+
          '<div data-pre-plain-text="time"><span class="selectable-text">Hello Krishna</span></div></div>';
        el.appendChild(row);
      }
    }""")
    assert web.outgoing(page,'Hello Krishna') == {'out','grouped'}
    page.locator('[data-id="in"]').evaluate('(e)=>e.remove()')
    assert web.outgoing(page,'Hello Krishna') == {'out'}
