# Claim checks

What Claim Karo checks before a claim can be filed. Claude only reads the photos; every
comparison is plain code in `api/services/rules.py`.

## Document checks (`rules.verify_details`)

Each upload is compared with the records saved when the policy was issued.

| # | Check | Photo | Fails with |
|---|---|---|---|
| 1 | Number plate = the insured vehicle's registration (spaces, dashes and case ignored) | Whole vehicle with damage | `PLATE_MISMATCH`, `PLATE_NOT_READABLE` |
| 2 | Licence number = the licence on the policy | Driving licence | `DL_NUMBER_MISMATCH`, `DL_NOT_READABLE` |
| 3 | Licence holder's name matches (word order free; one name may contain the other) | Driving licence | `DL_NAME_MISMATCH` |
| 4 | Licence valid on the accident date | Driving licence | `DL_EXPIRED_ON_INCIDENT_DATE`, `DL_VALIDITY_NOT_READABLE` |

- A photo that fails any of these is rejected and the user is told what didn't match. A
  retake is never accepted with a mismatch.
- Filing is checked again in `db.file_claim`: it refuses unless the vehicle photo and the
  licence are accepted with no mismatches. This covers filing from both the chat and the
  dashboard.

## Other checks

- **Photo quality** (Claude vision): blurry, too dark, plate or damage not visible, wrong
  subject. A second attempt with confidence ≥ 0.6 passes on quality alone.
- **Policy match** (`rules.match_policy`): same vehicle, accident date within the cover
  period, and the policy covers this kind of damage.
- **Exclusions** (`rules.viability`): conditions such as drunk driving, no valid licence or
  commercial use make the claim "not covered".

## Known gap

A licence that had expired on the accident date can't be fixed by uploading again, so the
claim stays at the photo step. The user can only cancel it.
