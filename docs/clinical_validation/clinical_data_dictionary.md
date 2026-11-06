# Prospective clinical data dictionary (planned)

This is a planning schema only; it does not authorize collection.

| Domain | Fields | Controls |
|---|---|---|
| Identity | pseudonymous participant ID, visit ID | key stored separately by authorized site; never names in model data |
| Reference | clinician diagnosis, reference date, assessor role, criteria/workup | source and uncertainty documented; no label inferred from voice |
| Demographics | age band or age, sex/gender only where justified | minimum necessary; pre-specified subgroup analysis |
| Clinical context | disease duration/stage, medication and time since dose if justified, voice-affecting conditions | consent, privacy review, defined coding; missingness retained |
| Acquisition | task, attempt, device make/model, OS/browser, codec, rate, distance, environment/noise, date/time | standardized protocol and QC metadata |
| Output | feature schema/version, quality flags, model version, result availability | no patient-identifying fields in feature vector; auditable versioning |

