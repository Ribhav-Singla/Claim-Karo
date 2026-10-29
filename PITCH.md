# Claim Karo — Paytm Build for India Pitch

## Title Slide

### Claim Karo
### Know before you claim.

**AI-powered insurance journeys for every Paytm customer**  
Track 2: AI-Powered Financial Journeys  
Team Claim Karo

---

## Stage Pitch

### The problem

Imagine your bike is damaged in an accident. The repair will cost ₹4,200.

You open your insurance app, but immediately face confusing policy terms, forms,
document requirements, photo uploads, and one important question:

**Should I even file this claim?**

Most insurance platforms are designed to help customers submit claims. But they
do not help customers understand whether claiming is financially beneficial.

A small claim can reduce the payout through deductibles and depreciation, while
also causing the customer to lose their No-Claim Bonus.

This makes insurance stressful, complex, and easy to get wrong.

### The solution

Meet **Claim Karo** — a voice-first, AI-powered insurance assistant designed for
the Paytm ecosystem.

A customer can simply speak in Hindi or English, describe the accident, and
upload damage photos.

Claim Karo then:

- Understands the incident through conversation
- Finds the relevant policy from the customer’s Paytm wallet
- Calculates the expected payout
- Accounts for deductibles, depreciation, IDV, exclusions, and No-Claim Bonus loss
- Tells the customer whether filing is worth it
- Checks whether photos meet surveyor requirements
- Pre-fills the claim form live
- Identifies missing documents
- Estimates settlement time
- Guides the customer through filing the claim

### Demo: When not to claim

Let’s take Ravi.

He says in Hindi:

> “Signal pe bike ko taxi ne maar diya. Mechanic ₹4,200 bata raha hai.”

Claim Karo matches his motor policy and performs the calculation.

The estimated payout is ₹2,130 after depreciation and deductibles. But filing
the claim would cost Ravi approximately ₹2,550 in lost No-Claim Bonus over the
next three years.

So instead of blindly pushing him to file, Claim Karo tells him:

> “Aapke liye claim karna financially beneficial nahi hai.”

This is a critical difference:

**Claim Karo does not just process claims. It protects customers from making
expensive decisions.**

### Demo: When to claim

Now consider Priya.

She says:

> “I hit a divider. The garage says ₹38,000.”

This time, her policy includes zero-depreciation coverage.

Claim Karo calculates:

- Expected payout: ₹37,000
- Potential No-Claim Bonus loss: ₹14,000

The recommendation is clear: **filing the claim makes financial sense.**

Priya uploads a damage photo. The AI detects that the number plate is not
visible and asks her to retake it.

After the correct photo and odometer image are uploaded, the claim form is
filled automatically.

Claim Karo identifies the missing driving licence, estimates a cashless
settlement timeline of 7 to 9 days, and lets Priya file the claim with a single
action.

## Proposed Solution

Claim Karo transforms insurance from a document-heavy process into a guided
financial conversation.

The customer does not need to understand insurance jargon. They only need to
explain what happened.

The assistant converts that conversation into:

1. A structured incident
2. A matched policy
3. A transparent financial recommendation
4. Verified evidence
5. A complete claim submission

## Technology Stack

Our technology stack combines AI with deterministic financial logic:

- **Next.js** for the customer-facing web experience
- **FastAPI and Python** for backend services
- **LiveKit** for real-time voice conversations
- **Sarvam AI** for Hindi-English speech recognition and text-to-speech
- **Claude** for incident extraction, explanations, and photo understanding
- **PostgreSQL** for claims, policies, evidence, and session state
- A deterministic **Python rules engine** for payout, deductible, depreciation,
  exclusion, and No-Claim Bonus calculations

Our core principle is:

### Rules decide. AI explains.

The AI never invents policy numbers or performs unchecked financial calculations.

## Unique Selling Proposition

Claim Karo’s USP is **financially intelligent claim guidance**.

Unlike traditional claim portals, it can recommend:

- **Claim**
- **Do not claim**
- **Borderline — review the numbers**
- **Not covered**

It also combines voice, multilingual support, image verification, live form
filling, and settlement estimation in one journey.

This makes insurance more accessible for users who may be uncomfortable
navigating complex English-first forms.

## Paytm Ecosystem Fit

Paytm already acts as a trusted financial companion for millions of Indians.

Claim Karo extends that trust into insurance by connecting:

- The customer’s Paytm wallet
- Their vehicles and policies
- A conversational AI assistant
- A transparent claim experience

The result is a more human insurance journey inside a familiar financial
ecosystem.

Instead of asking customers to search through policy documents, Claim Karo
brings the answer to them through conversation.

## Impact and Benefits

### For customers

- Reduces confusion and paperwork
- Supports Hindi and English conversations
- Prevents financially disadvantageous claims
- Improves photo and document quality
- Provides transparent payout calculations
- Gives confidence before filing

### For insurers and partners

- Fewer incomplete claim submissions
- Better-quality evidence
- Reduced manual clarification
- More accurate first-time submissions
- Faster processing and improved customer satisfaction

### For Paytm

- Deeper engagement with existing financial users
- A more intelligent insurance experience
- Increased trust across Paytm’s financial ecosystem
- A foundation for future insurance, lending, and fintech journeys

## Business Model

Claim Karo can be offered as a B2B2C insurance intelligence layer.

Potential revenue channels include:

- Per-claim processing fees from insurers
- SaaS licensing for insurers and brokers
- API access for embedded insurance partners
- Premium assisted-claims services
- Revenue sharing through Paytm insurance distribution

The long-term opportunity is to make Claim Karo a reusable conversational layer
for insurance and other complex financial journeys.

## Closing

Insurance should not feel like paperwork.

It should feel like a conversation with someone who understands your situation,
explains your options, and helps you make the right financial decision.

With Claim Karo, Paytm customers can know:

- What their policy covers
- What they may receive
- What documents they need
- How long it may take
- And most importantly — whether they should claim at all

### Claim Karo: Know before you claim.

Thank you.

## Suggested Final Slide

### Claim Karo
**AI-powered insurance journeys for Paytm customers**

**Speak. Understand. Decide. Claim.**

**Track 2 — AI-Powered Financial Journeys**  
Built with Claude + Sarvam AI + LiveKit
