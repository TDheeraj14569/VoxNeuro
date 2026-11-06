# Clinical workflow hypothesis

**Status: DESIGN ASSUMPTION. No local workflow has been observed.**

```text
Person notices movement / speech change
        → first-contact clinician gathers history and performs assessment
        → clinician considers differential causes and referral need
        → neurology / movement-disorder assessment and reference diagnosis
        → speech-language evaluation if indicated
        → follow-up with clinical measures and patient-reported function
```

VoxNeuro is currently outside this pathway: it is a local research tool for signal quality and acoustic feature review. A future clinician-reviewed report would require agreement on its intended decision role, acquisition protocol, population, harm controls, and clinical validity. Do not insert an experimental classifier into a patient's referral or treatment pathway.

## Map to replace after discovery

For each actual step, record: responsible role, input, output, handoff, time, failure mode, access barrier, technology, and evidence source. Explicitly validate the pathway separately for hospital, OPD, PHC, rehabilitation, home, and telemedicine settings.

