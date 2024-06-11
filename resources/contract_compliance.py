import json
import time

import rootpath

import requests
from requests.structures import CaseInsensitiveDict

from resources.contract_obligation import GetObligationIdentifierById, ObligationStatusUpdateById, \
    GetObligationByTermId, ObligationById
from resources.contract_terms import TermById, TermByObligationId, GetContractTerms
from resources.contractors import ContractorById
from resources.contracts import ContractByContractId, ContractStatusUpdateById, GetContractContractors, Contracts, \
    ContractByContractor, ContractByTermId

from resources.ccv_helper import CCVHelper

from resources.imports import *
from resources.schemas import *
from mailer import Mailer

from datetime import datetime, date
from timeit import default_timer as timer


class GetContractCompliance(MethodResource, Resource):
    @doc(description='Contract Compliance', tags=['Contract Compliance'])
    # @check_for_session
    # @Credentials.check_for_token
    # @marshal_with(BulkResponseQuerySchema)
    def get(self):
        query = QueryEngine()
        response = json.loads(
            query.select_query_gdb(purpose=None, dataRequester=None, additionalData="compliance", termID=None,
                                   contractRequester=None, contractProvider=None, ))

        print('scheduler')

        obligatons = response["results"]['bindings']
        current_datetime=str(datetime.now())
        current_date_time = CCVHelper.iso_date_conversion(self, current_datetime[:19])
        print(f"current date = {current_date_time}")
        # array for violation message
        all_violation_messages = []
        # array for total elapsed time
        total_elapsed_time=[]

        # loop over all obligations
        for x in obligatons:
            obligation_id = x["obligationId"]["value"]
            obligation_edate = x["endDate"]["value"][:19]
            obl_state = x["state"]["value"][45:]
            obl_desc = x["obligationDescription"]["value"]

            #  get terms
            get_term = TermByObligationId.get(self, obligation_id)
            my_json = get_term.data.decode('utf-8')
            data = json.loads(my_json)
            term_id = data['termId']

            # get contract by term
            contract = ContractByTermId.get(self, term_id)
            contract_data = contract.json
            contract_id = contract_data["contractId"]

            # initialize b2c data, b2b data, status and id
            b2c = b2c_contract_status = b2c_contract_id = ""
            b2b = b2b_contract_status = b2b_contract_id = ""
            b2cb2b = b2cb2b_contract_status = b2cb2b_contract_id = ""

            # initialize consent state
            consent = "empty"
            # consent="2e0c2cc4bc0c4e1b"

            # check the contract b2c or b2b
            if 'contb2c_' in contract_id:
                b2c = contract_id
            if 'contb2b_' in contract_id:
                b2b = contract_id
            if 'contb2cb2b' in contract_id:
                b2cb2b = contract_id


            # convert obligation end date time to date
            date_time_obj=CCVHelper.iso_date_conversion(self, obligation_edate)

            # get b2c contract
            b2c_data = ContractByContractId.get(self, b2c)
            b2c_data = b2c_data.json

            # get b2cb2b contract
            b2cb2b_data = ContractByContractId.get(self, b2cb2b)
            b2cb2b_data = b2cb2b_data.json

            # get consent id if contract is b2c
            if b2c_data != 'No data found for this ID':
                consent = b2c_data['consentId']

            if b2cb2b_data != 'No data found for this ID':
                consent = b2cb2b_data['consentId']


            # get b2b contract
            b2b_data = ContractByContractId.get(self, b2b)
            b2b_data = b2b_data.json

            if b2b_data != 'No data found for this ID':
                consent = b2b_data['consentId']
                b2b_contract_id = b2b_data["contractId"]
                b2b_contract_status = b2b_data["contractStatus"]

            if b2cb2b_data != 'No data found for this ID':
                consent = b2cb2b_data['consentId']
                b2cb2b_contract_id = b2cb2b_data["contractId"]
                b2cb2b_contract_status = b2cb2b_data["contractStatus"]

            if consent == "string" or consent == "":
                consent = "empty"

            # handle single business to business contract (first scenario)
            if b2b != "" and consent == "empty":


                # make shacl validation
                scenario = "ccv_first_scenario"
                iso_date_b2b_edate = CCVHelper.iso_date_conversion(self,b2b_data['endDate'][:19])
                iso_date_b2b_exdate = CCVHelper.iso_date_conversion(self,b2b_data['executionDate'][:19])
                iso_date_b2b_effdate = CCVHelper.iso_date_conversion(self,b2b_data['effectiveDate'][:19])
                # print(f"edate={iso_date_b2b_edate}")


                all_violation_messages.append(
                    CCVHelper.shacl_validation(self, scenario=scenario, contid=b2b_contract_id,
                                               conttype=b2b_data['contractType'],
                                               purpose=b2b_data['purpose'], contcategory=b2b_data['contractCategory'],
                                               contstatus=b2b_contract_status, enddate=iso_date_b2b_edate,
                                               effecdate=iso_date_b2b_effdate, exedate=iso_date_b2b_exdate,
                                               oblstate=obl_state, currentdate=current_date_time, consstate=consent))

                # actual check to detect violation

            if b2c_data != 'No data found for this ID':
                b2c_contract_id = b2c_data["contractId"]
                b2c_contract_status = b2c_data["contractStatus"]


            # handle business to consumer and business to business contract based on consent
            if b2cb2b != "" and consent != "empty":

                # get consent id from b2cb2b
                consent_id = b2cb2b_data["consentId"]

                # get consent state from automatic contacting tool (consent component)
                consent_state = CCVHelper.get_consent_state(self, consent_id)


                scenario = "ccv_second_scenario"
                iso_date_b2b_edate = CCVHelper.iso_date_conversion(self,b2cb2b_data['endDate'][:19])
                iso_date_b2b_exdate = CCVHelper.iso_date_conversion(self,b2cb2b_data['executionDate'][:19])
                iso_date_b2b_effdate = CCVHelper.iso_date_conversion(self,b2cb2b_data['effectiveDate'][:19])

                start = timer()
                all_violation_messages.append(
                    CCVHelper.shacl_validation(self, scenario=scenario, contid=b2cb2b_contract_id,
                                               conttype=b2cb2b_data['contractType'],
                                               purpose=b2cb2b_data['purpose'],
                                               contcategory="categoryBusinessToConsumer, base:categoryBusinessToBusiness",
                                               contstatus=b2cb2b_contract_status, enddate=iso_date_b2b_edate,
                                               effecdate=iso_date_b2b_effdate, exedate=iso_date_b2b_exdate,
                                               oblstate=obl_state, consstate=consent_state, currentdate=current_date_time))


            # handle single business to consumer contract based on consent
            elif b2c != "" and consent != "empty":



                consent_id = b2c_data["consentId"]
                consent_state = CCVHelper.get_consent_state(self, consent_id)

                scenario = "ccv_third_if_part_scenario"

                iso_date_b2c_edate = CCVHelper.iso_date_conversion(self,b2c_data['endDate'][:19])
                iso_date_b2c_exdate = CCVHelper.iso_date_conversion(self,b2c_data['executionDate'][:19])
                iso_date_b2c_effdate = CCVHelper.iso_date_conversion(self,b2c_data['effectiveDate'][:19])


                all_violation_messages.append(
                    CCVHelper.shacl_validation(self, scenario=scenario, contid=b2c_contract_id,
                                               conttype=b2c_data['contractType'],
                                               purpose=b2c_data['purpose'], contcategory=b2c_data['contractCategory'],
                                               contstatus=b2c_contract_status, enddate=iso_date_b2c_edate,
                                               effecdate=iso_date_b2c_effdate, exedate=iso_date_b2c_exdate,
                                               oblstate=obl_state, consstate=consent_state, currentdate=current_date_time))





                scenario = "ccv_third_else_part_scenario"
                iso_date_b2c_edate = CCVHelper.iso_date_conversion(self, b2c_data['endDate'][:19])
                iso_date_b2c_exdate = CCVHelper.iso_date_conversion(self, b2c_data['executionDate'][:19])
                iso_date_b2c_effdate = CCVHelper.iso_date_conversion(self, b2c_data['effectiveDate'][:19])
                consent_state = "Valid"

                all_violation_messages.append(
                        CCVHelper.shacl_validation(self, scenario=scenario, contid=b2c_contract_id,
                                                   conttype=b2c_data['contractType'],
                                                   purpose=b2c_data['purpose'],
                                                   contcategory=b2c_data['contractCategory'],
                                                   contstatus=b2c_contract_status, enddate=iso_date_b2c_edate,
                                                   effecdate=iso_date_b2c_effdate,
                                                   exedate=iso_date_b2c_exdate,
                                                   oblstate=obl_state, consstate=consent_state, currentdate=current_date_time))


            # handle single business to consumer contract

            elif b2c != "" and consent == "empty":


                scenario = "ccv_fourth_scenario"
                # print(scenario)
                print(f"b2c_datalala= {b2c_data}")
                iso_date_b2c_edate = CCVHelper.iso_date_conversion(self, b2c_data['endDate'][:19])
                iso_date_b2c_exdate = CCVHelper.iso_date_conversion(self, b2c_data['executionDate'][:19])
                iso_date_b2c_effdate = CCVHelper.iso_date_conversion(self, b2c_data['effectiveDate'][:19])


                all_violation_messages.append(
                    CCVHelper.shacl_validation(self, scenario=scenario, contid=b2c_contract_id,
                                               conttype=b2c_data['contractType'],
                                               purpose=b2c_data['purpose'], contcategory=b2c_data['contractCategory'],
                                               contstatus=b2c_contract_status, enddate=iso_date_b2c_edate,
                                               effecdate=iso_date_b2c_effdate, exedate=iso_date_b2c_exdate,
                                               oblstate=obl_state, currentdate=current_date_time,
                                               consstate=consent))




        return all_violation_messages
