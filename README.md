To run this application locally:

1. git clone https://github.com/GeniBushati/SHACL-contract-compliance-verification.git
2. Install GraphDB https://graphdb.ontotext.com/
3. Create repository on the GraphDB
4. Upload the test statements (from the test statements file) in the repository and make sure it is running. GraphDB will run on port 7200 locally.
5. Update the .env file with:
HOST_URI_GET='http://DESKTOP-FP4OP26:7200/repositories/repository-name'
HOST_URI_POST='http://DESKTOP-FP4OP26:7200/repositories/repository-name/statements'
6. Go to the backend folder of the contract compliance application
7. Run python app.py
8. Open the browser in http://127.0.0.1:5005/contract/compliance/
