# How Claim Karo decides "claim or don't claim"

Claim Karo answers one question: **is the money the insurer pays more than the
No-Claim Bonus (NCB) you lose by claiming?**

All of the maths lives in [`api/services/rules.py`](api/services/rules.py). The AI never
calculates anything; it only explains the result. All amounts are whole rupees, and
every division rounds down.

---

## 1. Inputs

| Input | Where it comes from |
|---|---|
| Repair estimate | What the user says the garage quoted |
| Own-damage (OD) premium | Policy |
| Current NCB % | Policy |
| Compulsory + voluntary deductible | Policy |
| Insured Declared Value (IDV) | Policy |
| Add-ons (`zero_dep`, `ncb_protect`) | Policy |
| Vehicle manufacture year | Vehicle |
| Incident date | User |

---

## 2. Formulas

### 2.1 Deductible

```
deductible = compulsory_deductible + voluntary_deductible
```

### 2.2 Depreciation %

Vehicle age is counted from 1 January of the manufacture year:

```
age_months = (incident_year − manufacture_year) × 12 + (incident_month − 1)
```

| Age (months) | < 6 | < 12 | < 24 | < 36 | < 48 | < 60 | 60 or more |
|---|---|---|---|---|---|---|---|
| Depreciation | 0% | 5% | 10% | 15% | 25% | 35% | 45% |

With the **`zero_dep`** add-on, depreciation is always **0%**.

### 2.3 Insurer payout

```
assessed     = min(repair_estimate, IDV)
depreciation = assessed × dep% ÷ 100
payout       = max(0, assessed − depreciation − deductible)
```

### 2.4 NCB loss over 3 years

Claiming resets the NCB to 0%. The loss is counted over the next three renewals.

- **Without a claim** the NCB keeps climbing the ladder:
  `0% → 20% → 25% → 35% → 45% → 50%` (it stops at 50%).
- **After a claim** it starts again from 0% and is only **20%** in year 2 and **25%** in
  year 3.

```
Year 1 loss = premium × current_NCB% ÷ 100
Year 2 loss = premium × (next_step(current_NCB%)  − 20%) ÷ 100
Year 3 loss = premium × (next_step(next_step(..)) − 25%) ÷ 100

NCB loss (3 years) = Year 1 + Year 2 + Year 3
```

`next_step` means one rung up the ladder (for example 20% → 25%, 25% → 35%).

With the **`ncb_protect`** add-on, the NCB loss is **₹0**.

### 2.5 Verdict

| Condition | Verdict |
|---|---|
| payout = 0 | `dont_claim` |
| payout ≤ NCB loss | `dont_claim` |
| payout ≤ NCB loss × 1.25 | `borderline` (the gain is too small to be clearly worth it) |
| otherwise | `claim` |

### 2.6 Breakeven estimate

This is the smallest repair bill at which the payout beats the NCB loss. It comes from
solving `estimate × (100 − dep%) ÷ 100 − deductible > NCB loss` for the estimate:

```
breakeven = (NCB_loss + deductible) × 100 ÷ (100 − dep%) + 1
```

The `+ 1` is there because the payout has to be strictly greater than the loss.

The breakeven is where claiming *starts* to pay. The verdict only becomes `claim` once
the payout is more than 1.25 × the NCB loss.

---

## 3. Worked example: Babu Khan's Ertiga, repair bill ₹6,500

Policy `POL-BABU-4W` (Bajaj General Insurance):

| Input | Value |
|---|---|
| Vehicle | Maruti Suzuki Ertiga ZXi (2022), `HR52H9260` |
| OD premium | ₹15,500 |
| Current NCB | 20% |
| Deductible | ₹1,000 compulsory + ₹0 voluntary |
| IDV | ₹7,80,000 |
| Add-ons | `zero_dep`, `rsa` |
| Repair estimate | ₹6,500 |

### Step 1: Deductible

```
deductible = 1,000 + 0 = ₹1,000
```

### Step 2: Depreciation

The policy has `zero_dep`, so:

```
dep% = 0%   (the car's age doesn't matter)
```

### Step 3: Payout

```
assessed     = min(6,500, 7,80,000) = ₹6,500
depreciation = 6,500 × 0 ÷ 100      = ₹0
payout       = 6,500 − 0 − 1,000    = ₹5,500
```

### Step 4: NCB loss

| Year | NCB without a claim | NCB after a claim | Gap | Loss = ₹15,500 × gap |
|---|---|---|---|---|
| 1 | 20% | 0% | 20% | **₹3,100** |
| 2 | 25% | 20% | 5% | **₹775** |
| 3 | 35% | 25% | 10% | **₹1,550** |
| | | | **Total** | **₹5,425** |

```
NCB loss = 3,100 + 775 + 1,550 = ₹5,425
```

> **Common mistake:** leaving out year 2 gives 3,100 + 1,550 = ₹4,650. Year 2 still
> costs ₹775, because without a claim the NCB would have been 25%, but after a claim it
> is only 20%.

### Step 5: Verdict

```
payout ≤ NCB loss ?          5,500 ≤ 5,425           → no
payout ≤ NCB loss × 1.25 ?   5,500 ≤ 6,781.25        → yes
```

**Verdict: `borderline`.** Claiming gains only 5,500 − 5,425 = **₹75**.

### Step 6: Breakeven

```
breakeven = (5,425 + 1,000) × 100 ÷ (100 − 0) + 1
          = 6,425 + 1
          = ₹6,426
```

At ₹6,426 the payout is ₹5,426, just ₹1 more than the NCB loss. The ₹6,500 bill is only
a little above this, which is why the verdict is borderline.

For the verdict to become `claim`, the payout must be more than ₹6,781.25, which needs
a repair bill of at least **₹7,782**.

### What the user hears

> Your insurer would pay ₹5,500, but you'd lose ₹5,425 of No-Claim Bonus over 3 years,
> so it's borderline. If you claim, the car may stay at the service centre for 3-4
> days, and the ₹1,000 file charge is free because you bought the policy through Paytm.

---

## 4. Second example, with depreciation: Babu Khan's Pulsar, bill ₹4,200

Policy `POL-BABU-2W`: OD premium ₹2,400, NCB 35%, deductible ₹100 + ₹500 voluntary,
no add-ons. Bajaj Pulsar 150, made in 2021, incident on 30 Oct 2026.

```
age_months   = (2026 − 2021) × 12 + (10 − 1) = 69     → 45% depreciation
deductible   = 100 + 500                     = ₹600
depreciation = 4,200 × 45 ÷ 100              = ₹1,890
payout       = 4,200 − 1,890 − 600           = ₹1,710
```

| Year | NCB without a claim | NCB after a claim | Gap | Loss = ₹2,400 × gap |
|---|---|---|---|---|
| 1 | 35% | 0% | 35% | ₹840 |
| 2 | 45% | 20% | 25% | ₹600 |
| 3 | 50% | 25% | 25% | ₹600 |
| | | | **Total** | **₹2,040** |

```
payout ≤ NCB loss ?   1,710 ≤ 2,040   → yes  →  dont_claim
breakeven = (2,040 + 600) × 100 ÷ (100 − 45) + 1 = 264,000 ÷ 55 + 1 = ₹4,801
```

**Verdict: `dont_claim`.** Claiming would cost Babu ₹330 more in lost bonus than the
insurer pays.

---

## 5. Where each formula lives in the code

| Formula | Function in `api/services/rules.py` |
|---|---|
| Deductible | `deductible()` |
| Vehicle age | `vehicle_age_months()` |
| Depreciation % | `depreciation_pct()` |
| NCB ladder step | `next_ncb()` |
| NCB loss | `ncb_loss()` |
| Breakeven | `_breakeven_estimate()` |
| Payout and verdict | `viability()` |
| "What if the bill is ₹X?" | `what_if()` |
