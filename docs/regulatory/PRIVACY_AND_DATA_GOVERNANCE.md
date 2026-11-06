# Privacy and data governance

The system processes raw voice in local session memory and does not persist audio or a report by default. UAMS and other voice recordings are kept out of Git. Voice can be identifying even when filenames contain pseudonymous codes, and repeated recordings can reveal identity. Do not use personal patient recordings without appropriate authority and consent.

For a future clinical or deployed version, complete a data-protection impact/threat assessment, define roles and purpose, minimize collection, obtain informed consent where required, control access, encrypt data at rest and in transit where deployment requires it, separate re-identification keys, set retention/deletion and backup policies, maintain audit logs, plan incident response, review third-party processors, and document patient rights and complaint handling.

India's Digital Personal Data Protection Act, 2023 and Digital Personal Data Protection Rules, 2025 are relevant official instruments; the Rules include phased commencement, so confirm the provisions in force at the point of collection/deployment. Obtain current legal advice rather than relying on this prototype document. [Official MeitY DPDP Rules listing](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa), [Gazette notification PDF](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf), [India Code Act record](https://www.indiacode.nic.in/indiacode/handle/123456789/22037?view_type=browse).

