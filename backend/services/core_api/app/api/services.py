"""Service registry endpoints — serves the pan-India service catalog to the frontend."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from civicflow_contracts.application import CategoryInfo, ServiceDetail, ServiceListItem
from civicflow_contracts.common import ServiceCategory, ServiceStatus

router = APIRouter()

# Pan-India service catalog — covers Central government and states/UTs across India
_SERVICE_CATALOG: list[dict] = [
    # --- Local Mock Service for Verified E2E Testing ---
    {
        "id": "mock-citizen-certificate",
        "title": "Income & Domicile Certificate (Local Mock Portal)",
        "category": ServiceCategory.certificates,
        "description": "Local test service running against the verified offline sandbox portal. Used for browser-assisted automation testing without contacting real government servers.",
        "jurisdiction": "Maharashtra",
        "department": "Revenue Department (Sandbox)",
        "official_url": "http://localhost:9090",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Eligibility", "Profile", "Documents", "Portal Sandbox", "Form Fill", "Review & Submit"],
        "eligibility_criteria": ["Open to all test applicants in local development", "Age 18+"],
        "required_documents": ["Identity Proof", "Address Proof", "Income Declaration"],
        "aliases": ["Mock portal", "Sandbox certificate", "Local test service", "Aaple sarkar mock"],
    },
    # --- Maharashtra ---
    {
        "id": "post-matric-scholarship",
        "title": "Post-Matric Scholarship (MahaDBT)",
        "category": ServiceCategory.education,
        "description": "Financial assistance for eligible students studying post-matric courses in Maharashtra.",
        "jurisdiction": "Maharashtra",
        "department": "Social Justice & Special Assistance Department",
        "official_url": "https://mahadbt.maharashtra.gov.in",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Eligibility", "Profile", "Documents", "Portal Login", "Form", "Review"],
        "eligibility_criteria": ["UG and PG students", "Maharashtra domicile", "Family annual income criteria apply"],
        "required_documents": ["Aadhaar Card", "Income Certificate", "Caste Certificate", "Previous Marksheet"],
        "aliases": ["MahaDBT", "Post matric", "Maharashtra scholarship", "EBC concession"],
    },
    {
        "id": "income-certificate-mh",
        "title": "Income Certificate (Aaple Sarkar)",
        "category": ServiceCategory.certificates,
        "description": "Official certificate of annual family income issued by the Revenue Department of Maharashtra.",
        "jurisdiction": "Maharashtra",
        "department": "Revenue Department",
        "official_url": "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/CitizenServices_RTS",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Service Requirements", "Profile", "Documents", "Portal Form", "Review"],
        "eligibility_criteria": ["Resident of Maharashtra", "Valid proof of family income"],
        "required_documents": ["Aadhaar Card", "Ration Card / Electricity Bill", "Salary Slip or Talathi Income Report"],
        "aliases": ["Aaple Sarkar Income", "Tahsil Income Certificate", "Uttapanna Dakhala"],
    },
    {
        "id": "domicile-certificate-mh",
        "title": "Domicile & Age/Nationality Certificate",
        "category": ServiceCategory.certificates,
        "description": "Proves 15+ years continuous residence in Maharashtra for educational and recruitment admissions.",
        "jurisdiction": "Maharashtra",
        "department": "Revenue Department",
        "official_url": "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/CitizenServices_RTS",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Confirm Jurisdiction", "Upload Residence Proof", "Complete Form", "Review"],
        "eligibility_criteria": ["Minimum 15 years residence in Maharashtra"],
        "required_documents": ["School Leaving Certificate", "Ration Card", "Electricity Bill / Rent Agreement", "Aadhaar Card"],
        "aliases": ["Adhivasi Dakhala", "Maharashtra Domicile", "Residence Certificate"],
    },
    {
        "id": "non-creamy-layer-mh",
        "title": "Non-Creamy Layer Certificate",
        "category": ServiceCategory.certificates,
        "description": "Certificate required for OBC/VJNT/SBC reservation in admissions and state public employment.",
        "jurisdiction": "Maharashtra",
        "department": "Revenue Department",
        "official_url": "https://aaplesarkar.mahaonline.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "information_only",
        "workflow_steps": ["Jurisdiction Check", "Income Verification", "Application Entry", "Tahsil Approval"],
        "eligibility_criteria": ["Belonging to notified OBC/VJNT/SBC category", "Family income under statutory threshold for last 3 years"],
        "required_documents": ["Caste Certificate", "3 Years Income Proof", "Aadhaar Card"],
        "aliases": ["NCL Certificate", "OBC Non Creamy Layer"],
    },

    # --- Bihar ---
    {
        "id": "caste-certificate-bihar",
        "title": "Caste Certificate (Jati Praman Patra - RTPS Bihar)",
        "category": ServiceCategory.certificates,
        "description": "Issuance of caste certificate by the Revenue Officer / SDO / DM in Bihar via RTPS ServicePlus.",
        "jurisdiction": "Bihar",
        "department": "General Administration Department",
        "official_url": "https://serviceonline.bihar.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Select Authority (RO/SDO/DM)", "Enter Applicant Details", "Upload Identity Proof", "Review & Submit"],
        "eligibility_criteria": ["Permanent resident of Bihar", "Belonging to recognized SC/ST/EBC/BC category"],
        "required_documents": ["Aadhaar Card", "Self-declaration", "Ration Card / Voter ID"],
        "aliases": ["RTPS Bihar", "Jati Praman Patra", "Bihar caste certificate", "ServicePlus Bihar"],
    },
    {
        "id": "income-certificate-bihar",
        "title": "Income Certificate (Aay Praman Patra - RTPS Bihar)",
        "category": ServiceCategory.certificates,
        "description": "Certificate of annual income for scholarship and welfare schemes issued by Revenue Officer in Bihar.",
        "jurisdiction": "Bihar",
        "department": "General Administration Department",
        "official_url": "https://serviceonline.bihar.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Select Block/Circle", "Income Sources Entry", "Verification", "Submit"],
        "eligibility_criteria": ["Permanent resident of Bihar"],
        "required_documents": ["Aadhaar Card", "Salary Certificate or Agriculture Income Declaration"],
        "aliases": ["Aay Praman Patra", "Bihar income certificate", "RTPS Aay"],
    },
    {
        "id": "residential-certificate-bihar",
        "title": "Residential Certificate (Niwas Praman Patra - RTPS Bihar)",
        "category": ServiceCategory.certificates,
        "description": "Proof of permanent or temporary residence in Bihar for government benefits.",
        "jurisdiction": "Bihar",
        "department": "General Administration Department",
        "official_url": "https://serviceonline.bihar.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Jurisdiction Select", "Residence Details", "Identity Upload", "Submit"],
        "eligibility_criteria": ["Residing in Bihar"],
        "required_documents": ["Aadhaar Card / Voter ID", "Photo"],
        "aliases": ["Niwas Praman Patra", "Bihar domicile", "RTPS Niwas"],
    },

    # --- Uttar Pradesh ---
    {
        "id": "income-certificate-up",
        "title": "Income Certificate (eDistrict UP)",
        "category": ServiceCategory.certificates,
        "description": "Official income certificate issued by the Board of Revenue, Uttar Pradesh for education and welfare.",
        "jurisdiction": "Uttar Pradesh",
        "department": "Revenue Department (Board of Revenue)",
        "official_url": "https://edistrict.up.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Citizen Registration", "Fill Application Form", "Upload Photo & Declaration", "Submit"],
        "eligibility_criteria": ["Citizen of Uttar Pradesh", "Family income verifiable by Lekhpal/Tehsildar"],
        "required_documents": ["Self-attested Declaration", "Salary Certificate or Lekhpal Report", "Ration Card"],
        "aliases": ["eDistrict UP", "UP Aay Praman Patra", "Uttar Pradesh income"],
    },
    {
        "id": "caste-certificate-up",
        "title": "Caste Certificate (Jati Praman Patra - eDistrict UP)",
        "category": ServiceCategory.certificates,
        "description": "Scheduled Caste, Scheduled Tribe, and OBC certificates issued by Tehsildar in Uttar Pradesh.",
        "jurisdiction": "Uttar Pradesh",
        "department": "Revenue Department",
        "official_url": "https://edistrict.up.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Tehsil Selection", "Caste Information", "Document Attachment", "Tehsildar Review"],
        "eligibility_criteria": ["Resident of Uttar Pradesh", "Member of recognized SC/ST/OBC community"],
        "required_documents": ["Aadhaar Card", "Caste proof of family member", "Self-declaration"],
        "aliases": ["UP Jati Praman", "eDistrict UP Caste"],
    },
    {
        "id": "domicile-certificate-up",
        "title": "Domicile / Residence Certificate (eDistrict UP)",
        "category": ServiceCategory.certificates,
        "description": "Certificate establishing bonafide residence in Uttar Pradesh for educational and job reservations.",
        "jurisdiction": "Uttar Pradesh",
        "department": "Revenue Department",
        "official_url": "https://edistrict.up.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Residence Details", "Upload Supporting Proofs", "Lekhpal Enquiry", "Issuance"],
        "eligibility_criteria": ["Continuous residence in UP for prescribed period"],
        "required_documents": ["Electricity Bill", "Voter Card / Aadhaar", "Educational Certificate"],
        "aliases": ["UP Niwas Praman", "UP Domicile"],
    },

    # --- National / Central Government ---
    {
        "id": "driving-license-renewal-national",
        "title": "Driving Licence Renewal (Parivahan Sarathi)",
        "category": ServiceCategory.licenses,
        "description": "Online application for renewal of non-transport and transport driving licences across India.",
        "jurisdiction": "National / Central Government",
        "department": "Ministry of Road Transport and Highways (MoRTH)",
        "official_url": "https://sarathi.parivahan.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Enter DL Number & DOB", "Select Services", "Upload Medical Certificate (Form 1A if age 40+)", "Fee Payment", "Slot Booking if required"],
        "eligibility_criteria": ["Holding an expired or expiring valid Indian Driving Licence", "Medical fitness compliance"],
        "required_documents": ["Existing Original DL", "Form 1A Medical Certificate (if age > 40)", "Address Proof"],
        "aliases": ["Parivahan", "Sarathi", "DL Renewal", "Driving licence", "RTO renewal"],
    },
    {
        "id": "national-scholarship-portal",
        "title": "Central Sector Scholarship (National Scholarship Portal - NSP)",
        "category": ServiceCategory.education,
        "description": "Common electronic portal for central government and UGC/AICTE scholarship schemes for minority, SC/ST, and merit students.",
        "jurisdiction": "National / Central Government",
        "department": "Ministry of Electronics and Information Technology / Ministry of Education",
        "official_url": "https://scholarships.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["One Time Registration (OTR)", "Scheme Selection", "Academic Profile", "Bank Account Details", "Institute Verification"],
        "eligibility_criteria": ["Enrolled in recognized school/college/university", "Scheme-specific income and merit guidelines"],
        "required_documents": ["Aadhaar Card", "Bonafide Student Certificate", "Income Certificate", "Caste Certificate if applicable"],
        "aliases": ["NSP", "National scholarship", "Central scholarship", "Minority scholarship"],
    },
    {
        "id": "passport-seva-reissue",
        "title": "Passport Reissue / Fresh Application (Passport Seva)",
        "category": ServiceCategory.registrations,
        "description": "Application for fresh passport or reissue of expiring/damaged passport through Passport Seva Kendra.",
        "jurisdiction": "National / Central Government",
        "department": "Ministry of External Affairs (Consular, Passport and Visa Division)",
        "official_url": "https://www.passportindia.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "information_only",
        "workflow_steps": ["User Registration", "Online Application Form", "Appointment Booking & Fee Payment", "Visit PSK with Originals"],
        "eligibility_criteria": ["Indian Citizen by birth, descent, or registration"],
        "required_documents": ["Proof of Date of Birth", "Proof of Present Address", "Old Passport (for reissue)"],
        "aliases": ["Passport Seva", "Tatkaal Passport", "Passport renewal", "MEA Passport"],
    },
    {
        "id": "aadhaar-address-update",
        "title": "Aadhaar Address Update (myAadhaar UIDAI)",
        "category": ServiceCategory.registrations,
        "description": "Online update of residential address in Aadhaar using valid supporting document or Head of Family (HoF) consent.",
        "jurisdiction": "National / Central Government",
        "department": "Unique Identification Authority of India (UIDAI)",
        "official_url": "https://myaadhaar.uidai.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Login with Aadhaar OTP", "Enter New Address", "Upload Valid Address Proof", "Payment of Service Fee", "SRN Tracking"],
        "eligibility_criteria": ["Possessing a valid 12-digit Aadhaar number with linked active mobile number"],
        "required_documents": ["Valid Proof of Address (Passport, Bank Statement, Voter ID, Ration Card, etc.)"],
        "aliases": ["UIDAI", "myAadhaar", "Aadhaar update", "Address change in Aadhaar"],
    },
    {
        "id": "epfo-uan-activation",
        "title": "EPFO Member UAN Activation & PF Transfer",
        "category": ServiceCategory.benefits,
        "description": "Activate Universal Account Number (UAN), manage Employee Provident Fund passbook, and submit online transfer claims.",
        "jurisdiction": "National / Central Government",
        "department": "Employees' Provident Fund Organisation (Ministry of Labour & Employment)",
        "official_url": "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
        "status": ServiceStatus.available,
        "integration_mode": "information_only",
        "workflow_steps": ["Activate UAN", "KYC Seeding", "Online Claim Submission", "Employer Verification"],
        "eligibility_criteria": ["Salaried employee enrolled under EPFO", "Aadhaar linked with UAN"],
        "required_documents": ["UAN Number", "Aadhaar Card", "Bank Account Passbook / Cancelled Cheque"],
        "aliases": ["EPFO", "PF withdrawal", "UAN login", "Provident fund"],
    },

    # --- Delhi (NCT) ---
    {
        "id": "income-certificate-delhi",
        "title": "Income Certificate (e-District Delhi)",
        "category": ServiceCategory.certificates,
        "description": "Issuance of income certificate by the Revenue Department of Government of NCT of Delhi.",
        "jurisdiction": "Delhi",
        "department": "Revenue Department, GNCTD",
        "official_url": "https://edistrict.delhigovt.nic.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Citizen Login", "Select Service", "Upload BPL/AAY Card or Salary Proof", "Physical/Field Verification", "Download Certificate"],
        "eligibility_criteria": ["Resident of Delhi for at least 3 years", "Income under prescribed limit"],
        "required_documents": ["Aadhaar Card", "Electricity / Water Bill", "Salary Slip or Self Declaration"],
        "aliases": ["eDistrict Delhi", "Delhi Income Certificate", "GNCTD revenue"],
    },
    {
        "id": "domicile-certificate-delhi",
        "title": "Domicile Certificate (e-District Delhi)",
        "category": ServiceCategory.certificates,
        "description": "Certificate verifying 3+ years continuous residence in National Capital Territory of Delhi.",
        "jurisdiction": "Delhi",
        "department": "Revenue Department, GNCTD",
        "official_url": "https://edistrict.delhigovt.nic.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Application Entry", "Proof of 3 Years Stay", "Field Verification", "SDM Approval"],
        "eligibility_criteria": ["Resident of Delhi continuously for minimum 3 years"],
        "required_documents": ["Continuous 3 Years Address Proof (School Certificate, Voter Card, Passport)", "Aadhaar Card"],
        "aliases": ["Delhi Domicile", "Niwas Praman Delhi"],
    },

    # --- Karnataka ---
    {
        "id": "income-caste-karnataka",
        "title": "Income & Caste Certificate (Seva Sindhu)",
        "category": ServiceCategory.certificates,
        "description": "Official Revenue Department certificate under Sakala services via Seva Sindhu portal.",
        "jurisdiction": "Karnataka",
        "department": "Revenue Department (Karnataka)",
        "official_url": "https://sevasindhu.karnataka.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Select Nadakacheri Circle", "Enter Aadhaar Details", "Income Disclosure", "Village Accountant Verification"],
        "eligibility_criteria": ["Resident of Karnataka", "Belonging to eligible income or category bracket"],
        "required_documents": ["Ration Card", "Aadhaar Card", "Salary Certificate or Agricultural Land Records (RTC)"],
        "aliases": ["Seva Sindhu", "Nadakacheri", "Karnataka Income", "Caste certificate Karnataka", "Sakala"],
    },
    {
        "id": "gruha-lakshmi-karnataka",
        "title": "Gruha Lakshmi Scheme (Seva Sindhu)",
        "category": ServiceCategory.benefits,
        "description": "Monthly financial assistance of ₹2,000 to woman head of the family in Karnataka.",
        "jurisdiction": "Karnataka",
        "department": "Department of Women & Child Development",
        "official_url": "https://sevasindhu.karnataka.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "information_only",
        "workflow_steps": ["Ration Card Verification", "Woman Head Selection", "Bank Account Linking (Aadhaar Seeded)", "Submission"],
        "eligibility_criteria": ["Woman head identified on Antyodaya/BPL/APL ration card", "Non-taxpayer"],
        "required_documents": ["Aadhaar Card of Woman Head & Husband", "Ration Card", "Bank Passbook"],
        "aliases": ["Gruha Lakshmi", "Karnataka 2000 scheme", "Seva Sindhu guarantee"],
    },

    # --- Tamil Nadu ---
    {
        "id": "community-certificate-tn",
        "title": "Community / Caste Certificate (e-Sevai Tamil Nadu)",
        "category": ServiceCategory.certificates,
        "description": "Community certificate issued by Zonal Deputy Tahsildar / Tahsildar through TNeGA e-Sevai portal.",
        "jurisdiction": "Tamil Nadu",
        "department": "Revenue and Disaster Management Department",
        "official_url": "https://www.tnesevai.tn.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["CAN Registration", "Fill Application", "Upload Documents", "VAO & RI Inspection", "Tahsildar Sign"],
        "eligibility_criteria": ["Resident of Tamil Nadu belonging to BC/MBC/DNC/SC/ST"],
        "required_documents": ["Applicant Photo", "Community Certificate of Parents/Siblings", "Aadhaar Card", "Smart Ration Card"],
        "aliases": ["TNeGA", "e-Sevai", "Tamil Nadu community certificate", "TN caste"],
    },
    {
        "id": "nativity-certificate-tn",
        "title": "Nativity / Domicile Certificate (e-Sevai TN)",
        "category": ServiceCategory.certificates,
        "description": "Certifies place of birth and continuous residence in Tamil Nadu for educational counselling and jobs.",
        "jurisdiction": "Tamil Nadu",
        "department": "Revenue Department",
        "official_url": "https://www.tnesevai.tn.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Enter CAN ID", "Provide 5+ Years Residence Details", "Upload Proof", "Issuance"],
        "eligibility_criteria": ["Born in Tamil Nadu or residing for minimum 5 consecutive years"],
        "required_documents": ["Birth Certificate", "School Transfer Certificate", "Family Card / Smart Card"],
        "aliases": ["Nativity certificate", "TN domicile", "eSevai nativity"],
    },

    # --- West Bengal ---
    {
        "id": "caste-certificate-wb",
        "title": "SC / ST / OBC Certificate (Oasis / e-District WB)",
        "category": ServiceCategory.certificates,
        "description": "Issuance of SC/ST/OBC certificate by Backward Classes Welfare Department, West Bengal.",
        "jurisdiction": "West Bengal",
        "department": "Backward Classes Welfare Department",
        "official_url": "https://castcertificatewb.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Online Application Registration", "Blood Relation Certificate Details", "Document Upload", "BDO / SDO Verification"],
        "eligibility_criteria": ["Permanent resident of West Bengal", "Blood relation proof or local enquiry"],
        "required_documents": ["EPIC / Voter Card", "Aadhaar Card", "Certificate of Blood Relation"],
        "aliases": ["Caste certificate WB", "West Bengal OBC", "e-District WB"],
    },
    {
        "id": "lakshmir-bhandar-wb",
        "title": "Lakshmir Bhandar Scheme (Duare Sarkar)",
        "category": ServiceCategory.benefits,
        "description": "Basic monthly income support for female heads of household aged 25-60 in West Bengal.",
        "jurisdiction": "West Bengal",
        "department": "Women and Child Development and Social Welfare Department",
        "official_url": "https://duaresarkar.wb.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "information_only",
        "workflow_steps": ["Duare Sarkar Camp / BDO Office", "Swasthya Sathi Card Verification", "Bank Account Registration", "Monthly DBT"],
        "eligibility_criteria": ["Female resident aged 25-60", "Enrolled in Swasthya Sathi"],
        "required_documents": ["Swasthya Sathi Card", "Aadhaar Card", "Bank Passbook"],
        "aliases": ["Lakshmir Bhandar", "Duare Sarkar", "WB women scheme"],
    },

    # --- Rajasthan ---
    {
        "id": "jan-aadhaar-rajasthan",
        "title": "Jan Aadhaar Card Registration & Update",
        "category": ServiceCategory.registrations,
        "description": "Single identity and entitlement database card for citizen families in Rajasthan.",
        "jurisdiction": "Rajasthan",
        "department": "Department of Information Technology & Communication (DOIT&C)",
        "official_url": "https://janaadhaar.rajasthan.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Family Head Entry", "Add Family Members", "Seed Bank & Aadhaar", "E-Mitra Verification"],
        "eligibility_criteria": ["Resident family of Rajasthan"],
        "required_documents": ["Aadhaar of all members", "Electricity Bill", "Bank Passbook of Female Head"],
        "aliases": ["Jan Aadhaar", "Bhamashah", "E-Mitra Rajasthan"],
    },
    {
        "id": "bonafide-certificate-rajasthan",
        "title": "Bonafide Resident (Mool Niwas) Certificate",
        "category": ServiceCategory.certificates,
        "description": "Certificate establishing bonafide residence in Rajasthan issued via E-Mitra / Single Sign On.",
        "jurisdiction": "Rajasthan",
        "department": "Revenue Department",
        "official_url": "https://sso.rajasthan.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["SSO Login", "Application Form", "Verification by Patwari", "Tehsildar Digital Sign"],
        "eligibility_criteria": ["Continuous stay of 10+ years in Rajasthan or born in Rajasthan"],
        "required_documents": ["Jan Aadhaar Card", "10 Years Residence Proof", "Self-declaration"],
        "aliases": ["Mool Niwas", "Rajasthan Domicile", "E-Mitra certificate"],
    },

    # --- Gujarat ---
    {
        "id": "income-certificate-gujarat",
        "title": "Income Certificate (Digital Gujarat)",
        "category": ServiceCategory.certificates,
        "description": "Annual income certificate issued by Talati / Mamlatdar via Digital Gujarat portal.",
        "jurisdiction": "Gujarat",
        "department": "Revenue Department",
        "official_url": "https://www.digitalgujarat.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Digital Gujarat Login", "Enter Family Income Details", "Upload Talati Report", "E-Sign & Issuance"],
        "eligibility_criteria": ["Resident of Gujarat"],
        "required_documents": ["Ration Card", "Electricity Bill", "Income Proof / Talati Roobroo Jawab"],
        "aliases": ["Digital Gujarat", "Gujarat Aavak Dakhlo", "Mamlatdar income"],
    },

    # --- Kerala ---
    {
        "id": "income-certificate-kerala",
        "title": "Income Certificate (e-District Kerala)",
        "category": ServiceCategory.certificates,
        "description": "Income certificate issued by Village Officer through e-District Kerala for educational fee concession.",
        "jurisdiction": "Kerala",
        "department": "Revenue Department",
        "official_url": "https://edistrict.kerala.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["One Time Registration", "Application Submission", "Village Officer Inspection", "Tahsildar Digital Approval"],
        "eligibility_criteria": ["Resident of Kerala"],
        "required_documents": ["Aadhaar Card", "Ration Card", "Salary Certificate or Village Enquiry Report"],
        "aliases": ["eDistrict Kerala", "Akshaya Kerala", "Kerala Income"],
    },

    # --- Madhya Pradesh ---
    {
        "id": "mool-niwas-mp",
        "title": "Permanent Resident (Mool Niwas) Certificate",
        "category": ServiceCategory.certificates,
        "description": "Permanent residence certificate under MP e-District Lok Seva Guarantee.",
        "jurisdiction": "Madhya Pradesh",
        "department": "Revenue Department / Public Service Management",
        "official_url": "https://mpedistrict.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Citizen Registration", "Samagra ID Entry", "Fill Form", "SDM Verification"],
        "eligibility_criteria": ["Continuous stay of 15 years in MP or born in MP"],
        "required_documents": ["Samagra Family ID", "Aadhaar Card", "Affidavit of Residence"],
        "aliases": ["MP eDistrict", "Lok Seva Kendra MP", "Samagra Domicile"],
    },

    # --- Odisha ---
    {
        "id": "resident-certificate-odisha",
        "title": "Resident / Domicile Certificate (e-District Odisha)",
        "category": ServiceCategory.certificates,
        "description": "Resident certificate issued by Tahsildar via Odisha e-District portal.",
        "jurisdiction": "Odisha",
        "department": "Revenue & Disaster Management Department",
        "official_url": "https://edistrict.odisha.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["ServicePlus Login", "Fill Form with RoR Details", "Upload Identity Proof", "Revenue Inspector Enquiry"],
        "eligibility_criteria": ["Continuous residence in Odisha for at least 1 year"],
        "required_documents": ["RoR (Record of Rights / Patta) or Rent Receipt", "Aadhaar Card"],
        "aliases": ["Odisha eDistrict", "Odisha Resident Certificate"],
    },

    # --- Andhra Pradesh & Telangana ---
    {
        "id": "integrated-certificate-ap",
        "title": "Integrated Certificate (Caste, Nativity, DOB - MeeSeva)",
        "category": ServiceCategory.certificates,
        "description": "Combined caste, nativity, and date of birth certificate for education and employment admissions.",
        "jurisdiction": "Andhra Pradesh",
        "department": "Revenue Department (AP MeeSeva)",
        "official_url": "https://vswsonline.ap.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["MeeSeva Login", "Enter Ration Card / Aadhaar", "Select Community", "VRO / Tahsildar Approval"],
        "eligibility_criteria": ["Permanent resident of Andhra Pradesh"],
        "required_documents": ["Aadhaar Card", "School Transfer Certificate", "Ration Card"],
        "aliases": ["MeeSeva AP", "AP Integrated Certificate", "Gram Ward Sachivalayam"],
    },
    {
        "id": "caste-certificate-telangana",
        "title": "Caste & Community Certificate (TG MeeSeva)",
        "category": ServiceCategory.certificates,
        "description": "Issued by Tahsildar for SC, ST, BC communities in Telangana via MeeSeva.",
        "jurisdiction": "Telangana",
        "department": "Revenue Department (Telangana)",
        "official_url": "https://ts.meeseva.telangana.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["MeeSeva Request", "Family Caste Details", "Tahsildar Sign", "Certificate Download"],
        "eligibility_criteria": ["Resident of Telangana belonging to recognized community"],
        "required_documents": ["Aadhaar Card", "Ration Card", "Applicant Photo"],
        "aliases": ["Telangana MeeSeva", "TS Caste Certificate"],
    },

    # --- Punjab ---
    {
        "id": "residence-certificate-punjab",
        "title": "Residence Certificate (Sewa Kendra Punjab)",
        "category": ServiceCategory.certificates,
        "description": "Issuance of residence certificate through e-Sewa Punjab portal.",
        "jurisdiction": "Punjab",
        "department": "Department of Governance Reforms",
        "official_url": "https://esewa.punjab.gov.in/",
        "status": ServiceStatus.available,
        "integration_mode": "civicflow_assisted",
        "workflow_steps": ["Citizen Registration", "Fill Form", "Halqa Patwari Report", "Sub-Divisional Magistrate Sign"],
        "eligibility_criteria": ["Resident of Punjab for 5+ years"],
        "required_documents": ["Voter Card", "Aadhaar Card", "Electricity Bill", "Verification Report"],
        "aliases": ["eSewa Punjab", "Sewa Kendra", "Punjab Domicile"],
    },
]

_CATEGORY_META = {
    "education": {"label": "Education & Scholarships", "description": "National and State scholarships, fee reimbursement, and student financial aid."},
    "certificates": {"label": "Certificates", "description": "Income, domicile, caste/community, non-creamy layer, and residence certificates across all States/UTs."},
    "licenses": {"label": "Licenses & Permits", "description": "Driving licenses, learner permits, transport renewals, and municipal permits."},
    "benefits": {"label": "Benefits & Subsidies", "description": "Direct Benefit Transfer (DBT), welfare assistance, social pensions, and housing subsidies."},
    "registrations": {"label": "Government Registrations", "description": "Aadhaar, Passport Seva, EPFO, voter enrollment, and citizen registry updates."},
    "other": {"label": "Other Services", "description": "Search for or describe another central, state, or municipal public service."},
}

import csv
import os

_CSV_CATEGORY_MAP = {
    "identity-certificates": ServiceCategory.certificates,
    "birth-death-marriage": ServiceCategory.certificates,
    "education-scholarships": ServiceCategory.education,
    "transport-vehicles": ServiceCategory.licenses,
    "business-licences": ServiceCategory.licenses,
    "pension-welfare": ServiceCategory.benefits,
    "ration-food": ServiceCategory.benefits,
    "agriculture-rural": ServiceCategory.benefits,
    "labour-employment": ServiceCategory.benefits,
    "land-property-revenue": ServiceCategory.registrations,
    "utilities-municipal": ServiceCategory.registrations,
    "grievance-rti": ServiceCategory.other,
}

_DOC_PRESETS = {
    ServiceCategory.certificates: ["Aadhaar Card", "Proof of Address (Electricity Bill / Ration Card)", "Self-Declaration / Affidavit", "Age Proof"],
    ServiceCategory.education: ["Aadhaar Card", "Admission Letter / College ID", "Previous Year Marksheet", "Income Certificate", "Bank Passbook"],
    ServiceCategory.licenses: ["Aadhaar / Voter ID", "Proof of Address", "Age Proof / Physical Fitness Certificate", "Photographs"],
    ServiceCategory.benefits: ["Aadhaar Card", "Bank Account Details / Passbook", "Income Certificate / BPL Card", "Category Proof"],
    ServiceCategory.registrations: ["Property Deed / Electricity Bill", "Aadhaar Card", "PAN Card", "Passport Photographs"],
    ServiceCategory.other: ["Aadhaar Card", "Grievance / Request Application Letter", "Supporting Documents"],
}

def _load_csv_services() -> list[dict]:
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "../../../../../CivicFlow_India_Service_Inventory_Important_Files_v1/national_service_seed_matrix.csv"),
        os.path.join(os.path.abspath("."), "CivicFlow_India_Service_Inventory_Important_Files_v1/national_service_seed_matrix.csv"),
        os.path.join(os.path.abspath("."), "national_service_seed_matrix.csv"),
    ]
    csv_file = None
    for p in possible_paths:
        if os.path.isfile(p):
            csv_file = p
            break
    if not csv_file:
        return []

    existing_ids = {s["id"] for s in _SERVICE_CATALOG}
    csv_records = []
    with open(csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            state_code = (row.get("state_code") or "").strip()
            raw_sid = (row.get("service_id") or "").strip().replace("_", "-")
            sid = f"{state_code.lower()}-{raw_sid}"
            if sid in existing_ids:
                continue
            title = (row.get("service_name") or "").strip()
            state_name = (row.get("state_or_ut") or "").strip()
            cat_raw = (row.get("category_id") or "").strip()
            cat = _CSV_CATEGORY_MAP.get(cat_raw, ServiceCategory.other)
            dept = (row.get("department_hint") or "").strip().replace(" | ", " & ")
            url = (row.get("primary_portal_url") or "").strip()

            desc = f"Official {title} service for citizens in {state_name}. Apply through the state government portal."
            docs = _DOC_PRESETS.get(cat, ["Aadhaar Card", "Proof of Identity", "Proof of Address"])

            csv_records.append({
                "id": sid,
                "title": f"{title} ({state_name})",
                "category": cat,
                "description": desc,
                "jurisdiction": state_name,
                "department": dept or f"{state_name} State Department",
                "official_url": url,
                "status": ServiceStatus.available,
                "integration_mode": "civicflow_assisted",
                "workflow_steps": ["Service Requirements", "Citizen Profile", "Document Verification", "Portal Access", "Form Review & Submission"],
                "eligibility_criteria": [f"Resident of {state_name}", "Valid Aadhaar / Identity proof", "Fulfillment of department guidelines"],
                "required_documents": docs,
                "aliases": [title, f"{title} {state_name}", state_code, raw_sid.replace("-", " ")],
            })
            existing_ids.add(sid)
    return csv_records

_SERVICE_CATALOG.extend(_load_csv_services())



@router.get("", response_model=list[ServiceListItem])
async def list_services(
    category: str | None = None,
    status: str | None = None,
    state: str | None = None,
    department: str | None = None,
    integration_mode: str | None = None,
    query: str | None = None,
):
    """List services with multi-factor search across state, category, status, department, and keywords."""
    results = _SERVICE_CATALOG

    if category:
        cat_lower = category.lower().strip()
        results = [s for s in results if s["category"].value.lower() == cat_lower]

    if status:
        stat_lower = status.lower().strip()
        results = [s for s in results if s["status"].value.lower() == stat_lower]

    if state:
        st_needle = state.lower().strip()
        results = [
            s for s in results
            if st_needle in (s.get("jurisdiction") or "").lower()
            or (st_needle in {"central", "national", "india"} and "national" in (s.get("jurisdiction") or "").lower())
        ]

    if department:
        dept_needle = department.lower().strip()
        results = [s for s in results if dept_needle in (s.get("department") or "").lower()]

    if integration_mode:
        mode_needle = integration_mode.lower().strip()
        results = [s for s in results if mode_needle in s.get("integration_mode", "").lower()]

    if query:
        needle = query.lower().strip()
        results = [
            s for s in results
            if needle in s["title"].lower()
            or needle in s["description"].lower()
            or needle in (s.get("jurisdiction") or "").lower()
            or needle in (s.get("department") or "").lower()
            or any(needle in alias.lower() for alias in s.get("aliases", []))
        ]

    return [
        ServiceListItem(
            id=s["id"],
            title=s["title"],
            category=s["category"],
            description=s["description"],
            jurisdiction=s.get("jurisdiction"),
            department=s.get("department"),
            status=s["status"],
            integration_mode=s.get("integration_mode", "information_only"),
            application_mode=s.get("application_mode", "catalog"),
            aliases=s.get("aliases", []),
        )
        for s in results
    ]


@router.get("/categories", response_model=list[CategoryInfo])
async def list_categories():
    """Return catalog categories with live count of services."""
    return [
        CategoryInfo(
            key=key,
            label=meta["label"],
            description=meta["description"],
            service_count=sum(1 for s in _SERVICE_CATALOG if s["category"].value == key),
        )
        for key, meta in _CATEGORY_META.items()
    ]


@router.get("/{service_id}", response_model=ServiceDetail)
async def get_service(service_id: str):
    """Retrieve full service details including official URL, eligibility criteria, and required documents."""
    for s in _SERVICE_CATALOG:
        if s["id"] == service_id:
            return ServiceDetail(
                id=s["id"],
                title=s["title"],
                category=s["category"],
                description=s["description"],
                jurisdiction=s.get("jurisdiction"),
                department=s.get("department"),
                status=s["status"],
                official_url=s.get("official_url"),
                workflow_steps=s.get("workflow_steps", []),
                eligibility_criteria=s.get("eligibility_criteria", []),
                required_documents=s.get("required_documents", []),
                integration_mode=s.get("integration_mode", "information_only"),
                application_mode=s.get("application_mode", "catalog"),
                aliases=s.get("aliases", []),
            )
    raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
