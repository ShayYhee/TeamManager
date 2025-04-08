# DocSystem
## 📄 Document Automation System

A Django-based internal web application for Business Development teams to streamline the generation, approval, and distribution of business documents like Approval Letters and SLA Agreements.

---

## 🚀 Features

- 🔐 Role-based access (BDA, BDM, Sales Rep, Admin)
- 📝 Document generation from templates using dynamic inputs
- 📄 Word to PDF conversion
- 👀 In-browser PDF preview via modal
- ✅ Approval workflow with status tracking
- 📧 Email delivery (via Zoho Mail) with CC to Sales Rep and BDM
- 📆 Date & user filters on document list
- 🔍 Column-specific filtering (company, type, status, created by, etc.)
- 🧹 Auto-cleanup of old files
- 📁 Local file storage with download & delete options

---

## 🛠 Tech Stack

- **Backend:** Django, Python
- **Frontend:** Bootstrap, HTML, JavaScript
- **PDF Conversion:** `python-docx`, `pdfkit`, `wkhtmltopdf`
- **Database:** SQLite / PostgreSQL
- **Email:** Zoho Mail SMTP Integration

---

## 📸 Screenshots

| Document List with Filters | PDF Preview Modal |
|----------------------------|-------------------|
| ![document list](screenshots/doc_list.png) | ![pdf modal](screenshots/pdf_preview.png) |

---

## ⚙️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/document-automation.git
cd document-automation
