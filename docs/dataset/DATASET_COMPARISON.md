# UAMS and UCI dataset comparison

| Property | UAMS Figshare voice samples | UCI dataset 470 |
|---|---|---|
| Source | University of Arkansas for Medical Sciences via Figshare | Cerrahpaşa Faculty of Medicine cohort via UCI |
| Data form | Raw telephone-collected WAV recordings and demographics workbook | Pre-extracted acoustic feature table (RAR/CSV) |
| Published cohort | 81 (40 PD, 41 controls) | 252 participants (188 PD, 64 controls), 756 repeated recordings |
| Task | Prolonged `/a/` | Sustained `/a/`, three repetitions per participant |
| Sampling information | Verify actual WAV headers; telephone collection reported | 44.1 kHz microphone reported |
| Feature compatibility | VoxNeuro extracts its own versioned schema | UCI-specific precomputed schema; not compatible with VoxNeuro features |
| Split unit | Participant ID | Participant ID, three repetitions grouped |
| Use in project | Small-cohort raw-audio feature experiment | Independent feature-only benchmark |

No dataset merging is planned. Domain, language, age/sex composition, clinical labels, hardware, features, and validation designs differ.

