export type ServiceStatus = "available" | "coming_soon" | "information_only"
export type ServiceCategory = "education" | "certificates" | "licenses" | "benefits" | "registrations" | "other"

export interface Service {
  id: string
  title: string
  category: ServiceCategory
  description: string
  jurisdiction?: string
  department?: string
  officialUrl?: string
  status: ServiceStatus
  integrationMode?: string
  workflowSteps?: string[]
  eligibility?: string[]
  documents?: string[]
  aliases?: string[]
}

import rawSeedServices from "./seedServices.json"

export const curatedServices: Service[] = [
  // Local Mock Service for Verified E2E Testing
  {
    id: "mock-citizen-certificate",
    title: "Income & Domicile Certificate (Local Mock Portal)",
    category: "certificates",
    description: "Local test service running against the verified offline sandbox portal. Used for browser-assisted automation testing without contacting real government servers.",
    jurisdiction: "Maharashtra",
    department: "Revenue Department (Sandbox)",
    officialUrl: "http://localhost:9090",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Eligibility", "Profile", "Documents", "Portal Sandbox", "Form Fill", "Review & Submit"],
    eligibility: ["Open to all test applicants in local development", "Age 18+"],
    documents: ["Identity Proof", "Address Proof", "Income Declaration"],
    aliases: ["Mock portal", "Sandbox certificate", "Local test service", "Aaple sarkar mock"]
  },
  // Maharashtra Services
  {
    id: "post-matric-scholarship",
    title: "Post-Matric Scholarship (MahaDBT)",
    category: "education",
    description: "Financial assistance for eligible students studying after Class 10.",
    jurisdiction: "Maharashtra",
    department: "Social Justice & Special Assistance Department",
    officialUrl: "https://mahadbt.maharashtra.gov.in",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Eligibility", "Profile", "Documents", "Portal Login", "Form", "Review"],
    eligibility: ["UG and PG students", "Maharashtra domicile", "Family income criteria apply"],
    documents: ["Aadhaar Card", "Income Certificate", "Previous Marksheet"],
    aliases: ["MahaDBT", "Post matric", "Maharashtra scholarship"]
  },
  {
    id: "income-certificate",
    title: "Income Certificate (Aaple Sarkar)",
    category: "certificates",
    description: "Request an official certificate of annual family income issued by Revenue Department.",
    jurisdiction: "Maharashtra",
    department: "Revenue Department",
    officialUrl: "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/CitizenServices_RTS",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Service Requirements", "Profile", "Documents", "Portal Login", "Form", "Review"],
    eligibility: ["Resident of Maharashtra", "Valid proof of family income"],
    documents: ["Aadhaar Card", "Address Proof", "Income Proof"],
    aliases: ["Aaple Sarkar Income", "Tahsil Income Certificate", "Uttapanna Dakhala"]
  },
  {
    id: "domicile-certificate",
    title: "Domicile & Residence Certificate",
    category: "certificates",
    description: "Understand requirements for proving 15+ years state residence in Maharashtra.",
    jurisdiction: "Maharashtra",
    department: "Revenue Department",
    officialUrl: "https://aaplesarkar.mahaonline.gov.in/en/CommonForm/CitizenServices_RTS",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Confirm service and issuing authority on official listing", "Follow listed application channel", "Review portal instructions"],
    eligibility: ["15+ years residence in Maharashtra"],
    documents: ["Identity Proof", "Address Proof", "School Leaving Certificate"],
    aliases: ["Adhivasi Dakhala", "Maharashtra Domicile"]
  },
  // Bihar Services
  {
    id: "caste-certificate-bihar",
    title: "Caste Certificate (Jati Praman Patra - RTPS Bihar)",
    category: "certificates",
    description: "Issuance of caste certificate by the Revenue Officer / SDO / DM in Bihar via RTPS ServicePlus.",
    jurisdiction: "Bihar",
    department: "General Administration Department",
    officialUrl: "https://serviceonline.bihar.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Select Authority (RO/SDO/DM)", "Enter Applicant Details", "Upload Identity Proof", "Review & Submit"],
    eligibility: ["Permanent resident of Bihar", "Belonging to recognized SC/ST/EBC/BC category"],
    documents: ["Aadhaar Card", "Self-declaration", "Ration Card / Voter ID"],
    aliases: ["RTPS Bihar", "Jati Praman Patra", "Bihar caste certificate", "ServicePlus Bihar"]
  },
  {
    id: "income-certificate-bihar",
    title: "Income Certificate (Aay Praman Patra - RTPS Bihar)",
    category: "certificates",
    description: "Certificate of annual income for scholarship and welfare schemes issued by Revenue Officer in Bihar.",
    jurisdiction: "Bihar",
    department: "General Administration Department",
    officialUrl: "https://serviceonline.bihar.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Select Block/Circle", "Income Sources Entry", "Verification", "Submit"],
    eligibility: ["Permanent resident of Bihar"],
    documents: ["Aadhaar Card", "Salary Certificate or Agriculture Income Declaration"],
    aliases: ["Aay Praman Patra", "Bihar income certificate", "RTPS Aay"]
  },
  // Uttar Pradesh Services
  {
    id: "income-certificate-up",
    title: "Income Certificate (eDistrict UP)",
    category: "certificates",
    description: "Official income certificate issued by the Board of Revenue, Uttar Pradesh for education and welfare.",
    jurisdiction: "Uttar Pradesh",
    department: "Revenue Department (Board of Revenue)",
    officialUrl: "https://edistrict.up.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Citizen Registration", "Fill Application Form", "Upload Photo & Declaration", "Submit"],
    eligibility: ["Citizen of Uttar Pradesh", "Family income verifiable by Lekhpal/Tehsildar"],
    documents: ["Self-attested Declaration", "Salary Certificate or Lekhpal Report", "Ration Card"],
    aliases: ["eDistrict UP", "UP Aay Praman Patra", "Uttar Pradesh income"]
  },
  {
    id: "caste-certificate-up",
    title: "Caste Certificate (Jati Praman Patra - eDistrict UP)",
    category: "certificates",
    description: "Scheduled Caste, Scheduled Tribe, and OBC certificates issued by Tehsildar in Uttar Pradesh.",
    jurisdiction: "Uttar Pradesh",
    department: "Revenue Department",
    officialUrl: "https://edistrict.up.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Tehsil Selection", "Caste Information", "Document Attachment", "Tehsildar Review"],
    eligibility: ["Resident of Uttar Pradesh", "Member of recognized SC/ST/OBC community"],
    documents: ["Aadhaar Card", "Caste proof of family member", "Self-declaration"],
    aliases: ["UP Jati Praman", "eDistrict UP Caste"]
  },
  // Delhi Services
  {
    id: "income-certificate-delhi",
    title: "Income Certificate (e-District Delhi)",
    category: "certificates",
    description: "Issuance of income certificate by the Revenue Department of Government of NCT of Delhi.",
    jurisdiction: "Delhi",
    department: "Revenue Department, GNCTD",
    officialUrl: "https://edistrict.delhigovt.nic.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Citizen Login", "Select Service", "Upload BPL/AAY Card or Salary Proof", "Physical/Field Verification", "Download Certificate"],
    eligibility: ["Resident of Delhi for at least 3 years", "Income under prescribed limit"],
    documents: ["Aadhaar Card", "Electricity / Water Bill", "Salary Slip or Self Declaration"],
    aliases: ["eDistrict Delhi", "Delhi Income Certificate", "GNCTD revenue"]
  },
  // Karnataka Services
  {
    id: "income-caste-karnataka",
    title: "Income & Caste Certificate (Seva Sindhu)",
    category: "certificates",
    description: "Official Revenue Department certificate under Sakala services via Seva Sindhu portal.",
    jurisdiction: "Karnataka",
    department: "Revenue Department (Karnataka)",
    officialUrl: "https://sevasindhu.karnataka.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Select Nadakacheri Circle", "Enter Aadhaar Details", "Income Disclosure", "Village Accountant Verification"],
    eligibility: ["Resident of Karnataka", "Belonging to eligible income or category bracket"],
    documents: ["Ration Card", "Aadhaar Card", "Salary Certificate or Agricultural Land Records (RTC)"],
    aliases: ["Seva Sindhu", "Nadakacheri", "Karnataka Income", "Caste certificate Karnataka", "Sakala"]
  },
  // Tamil Nadu Services
  {
    id: "community-certificate-tn",
    title: "Community / Caste Certificate (e-Sevai Tamil Nadu)",
    category: "certificates",
    description: "Community certificate issued by Zonal Deputy Tahsildar / Tahsildar through TNeGA e-Sevai portal.",
    jurisdiction: "Tamil Nadu",
    department: "Revenue and Disaster Management Department",
    officialUrl: "https://www.tnesevai.tn.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["CAN Registration", "Fill Application", "Upload Documents", "VAO & RI Inspection", "Tahsildar Sign"],
    eligibility: ["Resident of Tamil Nadu belonging to BC/MBC/DNC/SC/ST"],
    documents: ["Applicant Photo", "Community Certificate of Parents/Siblings", "Aadhaar Card", "Smart Ration Card"],
    aliases: ["TNeGA", "e-Sevai", "Tamil Nadu community certificate", "TN caste"]
  },
  // West Bengal Services
  {
    id: "caste-certificate-wb",
    title: "SC / ST / OBC Certificate (Oasis / e-District WB)",
    category: "certificates",
    description: "Issuance of SC/ST/OBC certificate by Backward Classes Welfare Department, West Bengal.",
    jurisdiction: "West Bengal",
    department: "Backward Classes Welfare Department",
    officialUrl: "https://castcertificatewb.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Online Application Registration", "Blood Relation Certificate Details", "Document Upload", "BDO / SDO Verification"],
    eligibility: ["Permanent resident of West Bengal", "Blood relation proof or local enquiry"],
    documents: ["EPIC / Voter Card", "Aadhaar Card", "Certificate of Blood Relation"],
    aliases: ["Caste certificate WB", "West Bengal OBC", "e-District WB"]
  },
  // National Services
  {
    id: "driving-license-renewal",
    title: "Driving Licence Renewal (Parivahan Sarathi)",
    category: "licenses",
    description: "Renew an existing driving licence through the Parivahan Sarathi national transport portal.",
    jurisdiction: "National / Central Government",
    department: "Ministry of Road Transport and Highways",
    officialUrl: "https://sarathi.parivahan.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Existing Application", "Authentication", "Details", "Documents", "Review"],
    eligibility: ["Holding valid expiring or expired driving licence"],
    documents: ["Existing Licence", "Medical Certificate (Form 1A if age 40+)"],
    aliases: ["Parivahan", "Sarathi", "DL renewal", "RTO renewal"]
  },
  {
    id: "national-scholarship-portal",
    title: "Central Sector Scholarship (National Scholarship Portal - NSP)",
    category: "education",
    description: "Common portal for Central Government and UGC/AICTE scholarship schemes for minority, SC/ST, and merit students.",
    jurisdiction: "National / Central Government",
    department: "Ministry of Electronics and Information Technology",
    officialUrl: "https://scholarships.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["One Time Registration (OTR)", "Scheme Selection", "Academic Profile", "Bank Account Details", "Institute Verification"],
    eligibility: ["Enrolled in recognized school/college/university", "Scheme-specific income and merit guidelines"],
    documents: ["Aadhaar Card", "Bonafide Student Certificate", "Income Certificate", "Caste Certificate if applicable"],
    aliases: ["NSP", "National scholarship", "Central scholarship"]
  },
  {
    id: "aadhaar-address-update",
    title: "Aadhaar Address Update (myAadhaar UIDAI)",
    category: "registrations",
    description: "Online update of residential address in Aadhaar using valid supporting document or Head of Family (HoF) consent.",
    jurisdiction: "National / Central Government",
    department: "Unique Identification Authority of India (UIDAI)",
    officialUrl: "https://myaadhaar.uidai.gov.in/",
    status: "available",
    integrationMode: "civicflow_assisted",
    workflowSteps: ["Login with Aadhaar OTP", "Enter New Address", "Upload Valid Address Proof", "Payment of Service Fee", "SRN Tracking"],
    eligibility: ["Possessing a valid 12-digit Aadhaar number with linked active mobile number"],
    documents: ["Valid Proof of Address (Passport, Bank Statement, Voter ID, Ration Card, etc.)"],
    aliases: ["UIDAI", "myAadhaar", "Aadhaar update", "Address change in Aadhaar"]
  },
  {
    id: "housing-subsidy",
    title: "Housing Subsidy (PMAY)",
    category: "benefits",
    description: "Explore housing support and credit linked subsidy eligibility information.",
    jurisdiction: "National / Central Government",
    department: "Housing and Urban Affairs",
    status: "information_only",
    integrationMode: "information_only",
    documents: ["Identity Proof", "Income Proof"]
  },
  {
    id: "public-registration",
    title: "Public Service Registration",
    category: "registrations",
    description: "Discover department-specific registration processes across Indian states.",
    jurisdiction: "National / Central Government",
    department: "CivicFlow directory",
    status: "coming_soon",
    integrationMode: "information_only"
  },
]

const existingIds = new Set(curatedServices.map((s) => s.id))
const nonDuplicateSeeds = (rawSeedServices as Service[]).filter((s) => !existingIds.has(s.id))

export const serviceCatalog: Service[] = [...curatedServices, ...nonDuplicateSeeds]

export const categoryMeta = {
  education: { label: "Education & Scholarships", description: "Scholarships, fee reimbursement, education grants and student benefits." },
  certificates: { label: "Certificates", description: "Income, domicile, caste, birth, and other official certificates across Indian States/UTs." },
  licenses: { label: "Licenses & Permits", description: "Driving, learner, trade and business permits." },
  benefits: { label: "Benefits & Subsidies", description: "Government subsidies, welfare benefits, pensions and financial assistance." },
  registrations: { label: "Government Registrations", description: "Public registrations and department-specific applications." },
  other: { label: "Other Services", description: "Search for or describe another government service." },
} as const
