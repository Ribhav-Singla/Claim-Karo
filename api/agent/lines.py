"""Fixed bot lines, so the common prompts never wait on Claude."""

from __future__ import annotations

from models import Language

LINES: dict[str, dict[Language, str]] = {
    "greeting": {
        "hi": "नमस्ते {name}! मैं Claim Karo हूँ। बताइए, आपकी गाड़ी के साथ क्या हुआ?",
        "en": "Hi {name}! I'm Claim Karo. Tell me what happened to your vehicle.",
    },
    "no_cover": {
        "hi": "माफ़ कीजिए, इस गाड़ी के लिए इस नुकसान पर आपकी पॉलिसी में कवर नहीं है।",
        "en": "Sorry, none of your policies cover this damage for this vehicle.",
    },
    "ask_photo": {
        "hi": "ठीक है, claim शुरू करते हैं। कृपया {kind} की फ़ोटो अपलोड करें।",
        "en": "Great, let's start the claim. Please upload a photo: {kind}.",
    },
    "next_photo": {
        "hi": "फ़ोटो ठीक है। अब {kind} की फ़ोटो अपलोड करें।",
        "en": "Got it. Now please upload a photo: {kind}.",
    },
    "advised_no_claim": {
        "hi": "ठीक है, claim नहीं करते। आपका No-Claim Bonus सुरक्षित है। ध्यान रखिए!",
        "en": "Okay, no claim then. Your No-Claim Bonus stays safe. Take care!",
    },
    "filed": {
        "hi": "आपका claim फ़ाइल हो गया। रेफ़रेंस नंबर {ref} है।",
        "en": "Your claim is filed. Your reference number is {ref}.",
    },
    "use_buttons": {
        "hi": "कृपया नीचे दिए बटन से चुनें।",
        "en": "Please choose using the buttons below.",
    },
    "upload_photo": {
        "hi": "कृपया फ़ोटो अपलोड करें।",
        "en": "Please upload the photo.",
    },
}

PHOTO_LABEL: dict[str, dict[Language, str]] = {
    "damage_wide": {
        "hi": "पूरी गाड़ी, नुकसान और नंबर प्लेट साफ़ दिखे",
        "en": "the whole vehicle with the damage and number plate visible",
    },
    "odometer": {"hi": "ओडोमीटर रीडिंग", "en": "the odometer reading"},
}

# Played on the call screen the moment the user stops talking, so the wait sounds like listening.
FILLERS: dict[Language, tuple[str, ...]] = {
    "hi": ("अच्छा…", "जी, एक सेकंड।", "ठीक है…"),
    "en": ("Okay…", "Got it, one sec.", "Mm-hmm…"),
}

# Spoken/typed words that count as a yes or no on the "claim karna hai?" question.
YES = ("haan", "han", "ha", "yes", "ok", "okay", "claim karo", "file", "हाँ", "हां", "जी")
NO = ("nahi", "nahin", "no", "mat", "नहीं", "ना")
