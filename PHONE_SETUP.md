# Calling Derek through the spare Airtel number

Updated: 2026-10-18. Device supplied by Kridey: **Samsung Galaxy A32 4G, Android, Airtel SIM**. Carrier corrected by Kridey from the earlier Jio description. The full phone number has not been collected or stored.

Status: **Feasibility researched; calls, forwarding, provider accounts and paid numbers are not configured.** Continue the shared assistant/voice build independently.

Current implementation: the local tray app, native voice window and Telegram poller are implemented, with live channel acceptance pending. Start with [LOCAL_APP.md](LOCAL_APP.md) and [VOICE_SETUP.md](VOICE_SETUP.md). Cloud hosting and the authenticated telephone adapter remain later steps; this local work has not changed any phone routing. Progress is tracked in [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md).

## Recommended route

```text
Your main phone calls the spare Airtel number
    -> Airtel forwards the call to an eligible Indian voice-gateway number
    -> authenticated gateway sends call audio to Derek in the cloud
    -> PIN + command interpretation + exact spoken confirmation
    -> result by speech and, when useful, Telegram/dashboard
```

This retains the spare number as the number you dial. A normal SIM in a normal Android handset does not provide the audio-streaming API needed by Derek. Android restricts the standard cellular call audio sources to privileged/system components; installing an ordinary app or connecting USB does not provide a dependable bidirectional call bridge. Rooting or accessibility workarounds are outside this implementation. [Android audio-source permissions](https://developer.android.com/reference/android/media/MediaRecorder.AudioSource)

Airtel documents call forwarding through handset/app methods for prepaid and postpaid connections. Confirm that the actual proposed Indian gateway destination is supported on this SIM before activation. The earlier Jio-specific destination exclusions and free-forwarding statement do not apply to this setup. Confirm forwarding eligibility and charges for the actual Airtel plan; gateway rental, streaming and model/speech usage need a separate quote. [Airtel forwarding setup](https://www.airtel.in/blog/airtel-app/activate-and-deactivate-call-forwarding-in-airtel/), [Airtel forwarding and charges guidance](https://www.airtel.in/blog/postpaid/call-forwarding-and-its-use/)

Exotel documents forwarding an existing number to an ExoPhone. The intended next step is to confirm that the personal-assistant use case qualifies for the needed Indian inbound number and bidirectional Voicebot streaming. Ownership of the Airtel SIM does not replace gateway eligibility, KYC or streaming approval. [Existing-number forwarding](https://exotel.com/features/call-forwarding-software/), [Exotel streaming onboarding](https://support.exotel.com/support/solutions/articles/3000132268-quick-guide-to-get-started-with-exotel-streaming-services)

## Setup order

1. Finish Derek's shared command/confirmation system and voice prototype, then host the service behind public HTTPS/WSS. Cloud call processing must work without the laptop.
2. Obtain provider confirmation of personal-use eligibility, suitable +91 destination, KYC, bidirectional streaming, caller-ID behavior and all recurring/per-minute charges. Record a budget before any purchase. Do not buy hardware or assume the existing SIM can be directly attached to the API.
3. Connect the provider adapter, enroll the permitted caller and set the DTMF PIN in the dashboard. Forwarded caller ID is a hint rather than authentication; verify its actual behavior in the eventual live call.
4. Only after the destination is verified and ready, follow Airtel's current handset/app instructions to enable voice-call forwarding to the approved Indian gateway number. Choose the forwarding type and confirm the destination; menus vary by handset/app version. Record the previous forwarding setting and the supported deactivation method so it can be restored. Do not use the earlier MyJio instructions. [Airtel instructions](https://www.airtel.in/blog/airtel-app/activate-and-deactivate-call-forwarding-in-airtel/)
5. Make a short owner call, authenticate, schedule one reminder, verify the readback/result and Telegram summary, then check provider charges. Check interruption, disconnect, unauthorized callers and the five-minute call cap before leaving it enabled.

For this dedicated spare number, unconditional forwarding is the intended eventual setting. It forwards all incoming calls, so leave the current setting unchanged until the gateway is ready. Keep an active Airtel plan and confirm any forwarding charges. Verify the carrier's behavior for switched-off/unreachable handsets during the live setup rather than assuming it.

If an eligible gateway is unavailable or the quote is unsuitable, leave PSTN calling disabled. Desktop voice and Telegram voice notes continue as independent channels. Native phone/browser calls over the internet can be a later option, but do not automatically substitute an international dial-in number.

## What is needed from Kridey

- Keep the Airtel SIM active and retain access to the carrier account/SIM verification.
- Later, review provider eligibility and the actual cost quote; complete KYC through the provider.
- Select the owner caller and PIN privately in the app when the phone adapter is ready.
- Participate in a short live call and forwarding/restore check at that stage.

No phone number, OTP, PIN or carrier account password needs to be pasted into chat now.
