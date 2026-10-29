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
    "plate_not_readable": {
        "hi": "नंबर प्लेट साफ़ नहीं पढ़ी जा रही। कृपया ऐसी फ़ोटो लें जिसमें नंबर प्लेट साफ़ दिखे।",
        "en": "I can't read the number plate. Please retake the photo with the plate visible.",
    },
    "plate_mismatch": {
        "hi": (
            "फ़ोटो में नंबर प्लेट {seen} है, पर आपकी बीमित गाड़ी का नंबर {expected} है। "
            "कृपया इसी गाड़ी की फ़ोटो अपलोड करें।"
        ),
        "en": (
            "The plate in this photo reads {seen}, but your insured vehicle is {expected}. "
            "Please upload a photo of that vehicle."
        ),
    },
    "dl_not_readable": {
        "hi": "लाइसेंस साफ़ नहीं पढ़ा जा रहा। कृपया लाइसेंस के सामने की तरफ़ की साफ़ फ़ोटो भेजें।",
        "en": "I can't read the licence. Please upload a sharp photo of the front of your licence.",
    },
    "dl_mismatch": {
        "hi": (
            "यह लाइसेंस पॉलिसी लेते समय दिए गए लाइसेंस (नंबर के आख़िरी अंक {last4}) से "
            "मेल नहीं खाता। कृपया वही लाइसेंस अपलोड करें।"
        ),
        "en": (
            "This licence doesn't match the one given when the policy was issued "
            "(number ending {last4}). Please upload that licence."
        ),
    },
    "dl_expired": {
        "hi": "यह लाइसेंस दुर्घटना की तारीख़ पर वैध नहीं था, इसलिए claim फ़ाइल नहीं हो सकता।",
        "en": "This licence wasn't valid on the date of the accident, so the claim can't be filed.",
    },
    "not_verified": {
        "hi": "claim फ़ाइल करने से पहले गाड़ी की फ़ोटो और ड्राइविंग लाइसेंस पॉलिसी से मेल खाने चाहिए।",
        "en": "Before filing, the vehicle photo and driving licence must match your policy.",
    },
}

PHOTO_LABEL: dict[str, dict[Language, str]] = {
    "damage_wide": {
        "hi": "पूरी गाड़ी, नुकसान और नंबर प्लेट साफ़ दिखे",
        "en": "the whole vehicle with the damage and number plate visible",
    },
    "odometer": {"hi": "ओडोमीटर रीडिंग", "en": "the odometer reading"},
    "dl": {"hi": "ड्राइविंग लाइसेंस (सामने की तरफ़)", "en": "your driving licence (front side)"},
}
