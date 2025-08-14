PDF Parser:
A simple web application built with Python and Flask that parses USB Power Delivery (PD) specification PDFs. It allows a user to upload a PDF, which is then processed to extract its structured content (based on the table of contents) into a downloadable JSON file.

Features:
Web-Based File Upload: An easy-to-use web interface for uploading PDF files.

Table of Contents Parsing: Intelligently identifies and parses the document's table of contents to understand its structure.

Section Content Extraction: Extracts the full text content for each section identified in the TOC.

JSON Output: Generates a clean, well-formatted, and human-readable JSON file as the final output for download.

Setup and Installation ⚙️
To get this project running on your local machine, follow these steps.

Navigate to the Project Directory
Open your terminal or command prompt and use the cd command to go to your project folder.

Bash

cd path/to/your_project_folder
Create a Virtual Environment (Recommended)
This step keeps your project's dependencies isolated from other Python projects.

Bash

# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
Install Dependencies
Install all the required Python packages using the requirements.txt file.

Bash

pip install -r requirements.txt
If you do not have a requirements.txt file, create one and add the following lines to it:
Flask
PyMuPDF
pdfplumber


How to Use the Application:
Run the Flask Server
With your terminal active in the project directory, run the main application script.

Bash

python app.py
Open in Browser
The terminal will show a message that the server is running, typically on http://127.0.0.1:5000. Copy this URL and paste it into your web browser.

Upload and Parse

Click the upload area to select a USB PD specification PDF from your computer.

Once a file is selected, the "Parse and Download JSON" button will become active.

Click the button to process the file. Your browser will automatically prompt you to download the resulting .json file.

Technology Stack 💻
Backend: Python, Flask

PDF Parsing: PyMuPDF (fitz), pdfplumber

Frontend: HTML5, CSS3
