"""Real harmless subprocess acceptance; never interrupts an installed service."""
import os
import time
from unittest.mock import patch
import pytest
import psutil
from desktop.process_group import ProcessGroup, stop_spawned_process
from desktop.supervisor import Supervisor


@pytest.mark.skipif(os.name != 'nt', reason='Windows process containment acceptance')
def test_owned_fixture_crash_is_restarted_and_contained(tmp_path):
    marker = tmp_path / 'started.txt'
    code = f"from pathlib import Path; import time; Path({str(marker)!r}).write_text('ready'); time.sleep(60)"
    with patch('desktop.supervisor.child_environment',return_value={}):
        owner=Supervisor(open_page=False)
    owner.services={'fixture':['-c',code]}
    owner.process_group=ProcessGroup()
    def ready():
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if marker.exists(): return
            time.sleep(.05)
        pytest.fail('Harmless fixture failed to start')
    try:
        with patch('desktop.supervisor.RUNTIME',tmp_path), patch('desktop.supervisor.write_record'):
            owner.launch('fixture'); ready()
            original=owner.processes['fixture']
            stop_spawned_process(original)
            assert original.poll() is not None
            marker.unlink()
            owner.monitor_service('fixture',original)
            assert owner.issues['service_fixture']=='ServiceExited'
            owner.retry_at['fixture']=0
            owner.monitor_service('fixture',original); ready()
            replacement=owner.processes['fixture']
            assert replacement.pid != original.pid and replacement.poll() is None
            assert 'service_fixture' not in owner.issues
            parent = psutil.Process(replacement.pid)
            owned_tree = [parent, *parent.children(recursive=True)]
            owner.process_group.close()
            replacement.wait(timeout=8)
            assert replacement.poll() is not None
            _, alive = psutil.wait_procs(owned_tree, timeout=8)
            assert not alive, 'A captured fixture descendant survived containment close'
    finally:
        for process in owner.processes.values(): stop_spawned_process(process)
        owner.process_group.close()
        for stream in owner.logs.values(): stream.close()
