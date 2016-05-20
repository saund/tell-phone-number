#!/usr/bin/python -tt

#dialogAgent.py is for an Agent model for a dialog management system to
#transmit structured data between a transmitter and a receiver using 
#natural, human-like conversational dialogue.
#
#A DialogAgent holds two DialogModels.  One DialogModel represents their
#own state of belief, while the other represents their state of belief about
#their conversation partner.   (In the future this framework might support
#3-way conversations and more.)
#
#A DialogModel holds belief state consisting of belief about the topic 
#of the dialogue (the DataModel), plus additional belief related to dialog
#management such as readiness, turn, and data communication protocol.
#


import csv
import random
import sys
import copy
import re
import os
import math
import ruleProcessing as rp



#Test just the rules in isolated-rules-test.txt
def loopDialogTest():
    rp.initLFRules('isolated-rules-test.txt')
    loopDialogMain()


gl_agent = None

    
#Test the rules in gl_default_lf_rule_filename.
#Loop one input and print out the set of DialogActs interpreted
def loopDialog():
    global gl_agent
    gl_agent = createBasicAgent()
    rp.initLFRulesIfNecessary()
    loopDialogMain()


def loopDialogMain():
    input_string = raw_input('Input: ')
    input_string = rp.removePunctuationAndLowerTextCasing(input_string)
    while input_string != 'stop' and input_string != 'quit':
        #print '\n' + input_string
        rule_match_list = rp.applyLFRulesToString(input_string)
        if rule_match_list == False:
            print 'no DialogRule matches found'
        else:
            print 'MATCH: ' + str(rule_match_list);
        da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)

        response_da_list = generateResponseToInputDialog(da_list)

        #print 'got ' + str(len(da_list)) + ' DialogActs'
        #print 'raw: ' + str(da_list)
        output_word_list = []
        for da in response_da_list:
            #print 'intent:' + da.intent
            #print 'arg_list: ' + str(da.arg_list)
            da.printSelf()
            da_generated_word_list = rp.generateTextFromDialogAct(da)
            if da_generated_word_list == None:
                print 'could not generate a string from da'
            else:
                output_word_list.extend(da_generated_word_list)
            #print 'lfs: ' + str(da.arg_list)
            #for lf in da.arg_list:
            #    lf.printSelf()

        str_generated = ' '.join(output_word_list)
        print 'gen: ' + str_generated

        input_string = raw_input('\nInput: ')




#Returns an Agent that is either a sender ('send') or receiver ('receive') of a telephone number
#that should be ready to engage in dialogue.
def createBasicAgent():
    agent = DialogAgent()
    agent.name = 'computer'
    agent.partner_name = 'person'
    #These get set when the agent determines to either send or receive a phone number
    #agent.send_receive_role = send_or_receive
    #agent.self_dialog_model = initDialogModel('self', send_or_receive)
    #agent.partner_dialog_model = initDialogModel('partner', sendReceiveOpposite(send_or_receive))
    return agent




def sendReceiveOpposite(send_or_receive):
    if send_or_receive == 'send':
        return 'receive'
    elif send_or_receive == 'receive':
        return 'send'
    else:
        print 'sendReceiveOpposite() got invalid arg ' + send_or_receive
        return None


class DialogAgent():
    def __init__(self):
        self.name = None
        self.partner_name = None
        self.send_receive_role = 'banter'     #'send' or 'receive' or 'banter'
        self.self_dialog_model = None
        self.partner_dialog_model = None

    #If the role is send, then the DialogAgent will be initialized with a send_phone_number which will
    #be stuffed into the self_dialog_model.  The DialogAgent will be initialized believing that the 
    #recipient has no information about the phone number.
    #If the role is receive, then the send_phone_number will be None and the communction partner 
    #will be responsible for obtaining the phone number they speak to the DialogAgent, 
    #and the DialogAgent will start off with no information about the phone number.
    def setRole(send_or_receive, send_phone_number=None):
        self.send_receive_role = send_or_receive
        if send_or_receive == 'banter':
            self.self_dialog_model = initBanterDialogModel('self')
            self.partner_dialog_model = initBanterDialogModel('partner')
            return None
        #phone number will only be used by the sending DialogModel
        self.self_dialog_model = initSendReceiveDataDialogModel('self', send_or_receive, send_phone_number)
        self.partner_dialog_model = initSendReceiveDataDialogModel('partner', sendReceiveOpposite(send_or_receive))
        return None

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = 'DialogAgent: ' + self.name
        pstr += '     partner: ' + self.partner_name + '\n'
        pstr += 'role: ' + self.send_receive_role + '\n\n'
        pstr += self.self_dialog_model.getPrintString() + '\n'
        pstr += self.partner_dialog_model.getPrintString() + '\n'
        return pstr


gl_default_phone_number = '6506371212'

def initSendReceiveDataDialogModel(self_or_partner, send_or_receive, send_phone_number=None):
    global gl_default_phone_number
    dm = DialogModel()
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    if send_or_receive == 'send':
        dm.data_model.setPhoneNumber(send_phone_number)
    dm.data_index_pointer = OrderedMultinomialBelief()
    dm.data_index_pointer.initAllConfidenceInOne([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 0)   #initialize starting at the first digit
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = BooleanBelief()
    dm.turn.setBeliefInTrue(.5)                                         #initialize not knowing whose turn it is
    dm.protocol_chunk_size = OrderedMultinomialBelief()
    dm.protocol_chunk_size.initAllConfidenceInOne([1, 2, 3, 10], 3)     #initialize with chunk size 3
    dm.protocol_handshaking = OrderedMultinomialBelief()
    dm.protocol_handshaking.initAllConfidenceInOne([1, 2, 3, 4, 5], 3)  #initialize with moderate handshaking
    return dm



    

#There will be one DialogModel for owner=self and one for owner=other-speaker
class DialogModel():
    def __init__(self):
        self.model_for = None       #one of 'self', 'partner'
        
        #for this application...
        self.data_model = None                   #A DataModel_USPhoneNumber
        self.data_index_pointer = None           #An OrderedMultinomialBelief: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

        #should be generic for all data communication applications
        self.readiness = None                    #A BooleanBelief: 1 = ready, 0 = not
        self.turn = None                         #A BooleanBelief: 1 = self, 0 = other-speaker
        self.protocol_chunck_size = None         #An OrderedMultinomialBelief: [1, 2, 3, 10]
        self.protocol_handshaking = None         #An OrderedMultinomialBelief: [1, 2, 3, 4, 5]  1 = never, 5 = every turn

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = 'DialogModel for ' + self.model_for + '\n'
        pstr += 'data_model_abbrev: ' + self.data_model.getPrintStringAbbrev() + '\n'
        pstr += 'data_model: ' + self.data_model.getPrintString() + '\n'
        pstr += 'data_index_pointer: ' + self.data_index_pointer.getPrintString() + '\n'
        pstr += 'readiness: ' + self.readiness.getPrintString() + '\n'
        pstr += 'turn: ' + self.turn.getPrintString() + '\n'
        pstr += 'chunk_size: ' + self.protocol_chunk_size.getPrintString() + '\n'
        pstr += 'handshaking: ' + self.protocol_handshaking.getPrintString() + '\n'
        return pstr

        



class DataModel():
    def __init__(self):
        self.data_type = None       #e.g. 'us-phone-number'
        self.owner = None
        self.data_beliefs = None     



class DataModel_USPhoneNumber(DataModel):
    def __init__(self):
        self.type = 'us-phone-number'
        self.data_beliefs = [DigitBelief(), DigitBelief(), DigitBelief(),\
                             DigitBelief(), DigitBelief(), DigitBelief(),\
                             DigitBelief(), DigitBelief(), DigitBelief(), DigitBelief()]
        self.data_indices = {'area_code':[0,2],\
                             'prefix':[3,5],\
                             'last-four-digits':[6,9]}


    #phone_number_string is like '3452233487', i.e. ten digits in a row
    def setPhoneNumber(self, phone_number_string):
        if len(phone_number_string) != 10:
            print 'setPhoneNumber got a phone_number_string: ' + phone_number_string + ' that is not 10 digits long'
            return
        for i in range(0, 10):
            numerical_digit = phone_number_string[i]
            word_digit = numericalDigitToWordDigit(numerical_digit)
            self.data_beliefs[i].setValueDefinite(word_digit)


    #digit_value is a string
    def setNthPhoneNumberDigit(self, nth, digit_value):
        self.data_beleifs[nth].setValueDefinite(digit_value)

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = '( ' + self.data_beliefs[0].getPrintString() + ' '\
                    + self.data_beliefs[1].getPrintString() + ' '\
                    + self.data_beliefs[2].getPrintString() + ' ) '\
                    + self.data_beliefs[3].getPrintString() + ' '\
                    + self.data_beliefs[4].getPrintString() + ' '\
                    + self.data_beliefs[5].getPrintString() + ' - '\
                    + self.data_beliefs[6].getPrintString() + ' '\
                    + self.data_beliefs[7].getPrintString() + ' '\
                    + self.data_beliefs[8].getPrintString() + ' '\
                    + self.data_beliefs[9].getPrintString() + ' )'
        return pstr

    def getPrintStringAbbrev(self):
        pstr = '(' + self.data_beliefs[0].getPrintStringAbbrev() + \
                     self.data_beliefs[1].getPrintStringAbbrev() + \
                     self.data_beliefs[2].getPrintStringAbbrev() + ') ' +\
                     self.data_beliefs[3].getPrintStringAbbrev() + \
                     self.data_beliefs[4].getPrintStringAbbrev() + \
                     self.data_beliefs[5].getPrintStringAbbrev() + '-' +\
                     self.data_beliefs[6].getPrintStringAbbrev() + \
                     self.data_beliefs[7].getPrintStringAbbrev() + \
                     self.data_beliefs[8].getPrintStringAbbrev() + \
                     self.data_beliefs[9].getPrintStringAbbrev()
        return pstr

            

                        



#A DigitBelief holds a distribution of beliefs over values of a digit from 0-9.
#The distribution can have at most three elements, val1, val2, and unknown.
#Probability is distributed among these
class DigitBelief():
    def __init__(self):
        self.val1_value = '-'        #value doesn't matter if the confidence is 0
        self.val1_confidence = 0.0
        self.val2_value = '-'        #value doesn't matter if the confidence is 0
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 1.0
        
    def setValueDefinite(self, value):
        self.val1_value = value
        self.val1_confidence = 1.0
        self.val2_value = '-'
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 0.0

    def setValueUnknown(self):
        self.val1_value = '-'
        self.val1_confidence = 0.0
        self.val2_value = '-'
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 1.0

    #returns a tuple (value, confidence)
    def getHighestConfidenceValue(self):
        max_confidence = max(self.val1_confidence, self.val2_confidence, self.val_unknown_confidence)
        if max_confidence == self.val1_confidence:
            return (self.val1_value, self.val1_confidence)
        elif max_confidence == self.val2_confidence:
            return (self.val2_value, self.val2_confidence)
        else:
            return ('?', self.val_unknown_confidence)
        

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        temp_list = [(self.val1_value, self.val1_confidence),\
                     (self.val2_value, self.val2_confidence),\
                     ('?', self.val_unknown_confidence)]
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        temp_list.reverse()
        return '[ \'' + str(temp_list[0][0]) + '\':' + format(temp_list[0][1], '.2f') + ', \''\
            + str(temp_list[1][0]) + '\':' + format(temp_list[1][1], '.2f') + ', \''\
            + str(temp_list[2][0]) + '\':' + format(temp_list[2][1], '.2f') + ' ]'

    def getPrintStringAbbrev(self):
        temp_list = [(self.val1_value, self.val1_confidence),\
                     (self.val2_value, self.val2_confidence),\
                     ('?', self.val_unknown_confidence)]
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        temp_list.reverse()
        return str(temp_list[0][0])




#A BooleanBelief represents belief distributed between the value 0=false and 1=true
#In other words, this is a binomial.
class BooleanBelief():
    def __init__(self):
        self.true_confidence = .5  #belief in the value 1=true, initialize as totally unknown

    def setBeliefInTrue(self, val):
        self.true_confidence = val

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        return '[ ' + format(self.true_confidence, '.2f') + ' ]'
        


#An OrderedMultinomialBelief represents belief distributed between several ordered values.
class OrderedMultinomialBelief():
    def __init__(self):
        self.value_name_confidence_list = None   #each element is a list [value, confidence]

    def initEquallyDistributed(self, value_list):
        self.value_name_confidence_list = []
        conf = 1.0 / len(value_list)
        for i in range(0, len(value_list)):
            self.value_name_confidence_list.append([value_list[i], conf])

    def initAllConfidenceInOne(self, value_list, all_confidence_value):
        self.value_name_confidence_list = []
        for i in range(0, len(value_list)):
            this_value = value_list[i]
            if this_value == all_confidence_value:
                conf = 1.0
            else:
                conf = 0.0
            self.value_name_confidence_list.append([this_value, conf])

    def getDominantValue(self):
        max_confidence = 0.0
        max_value = -1
        for i in range(0, len(self.value_name_confidence_list)):
            value_name_confidence = self.value_name_confidence_list[i]
            confidence = value_name_confidence[1]
            if confidence > max_confidence:
                max_confidence = confidence
                max_value = value_name_confidence[0]
        return max_value

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        conf_threshold_to_print = .1     #only print confidences > threshold .1
        temp_list = self.value_name_confidence_list[:]
        temp_list.sort(key = lambda tup: tup[1])  # sorts in place
        temp_list.reverse()
        ret_str = '[ '
        ret_str += str(temp_list[0][0]) + ':' + format(temp_list[0][1], '.2f')
        i = 1;
        while i < 3:
            if temp_list[i][1] > conf_threshold_to_print:
                ret_str += ' / ' + str(temp_list[i][0]) + ':' + format(temp_list[i][1], '.2f')
            i += 1
        ret_str += ' ]'
        return ret_str


gl_number_to_word_map = {'1':'one', '2':'two', '3':'three', '4':'four', '5':'five'\
                         '6':'six', '7':'seven', '8':'eight', '9':'nine', '0':'zero'}

def numericalDigitToWordDigit(numerical_digit):
    global gl_number_to_word_map
    return gl_number_to_word_map.get(numerical_digit)

#
#
###############################################################################

###############################################################################
#
#
#


def generateResponseToInputDialog(da_list):

    if len(da_list) == 0:
        return da_list
    
    if da_list[0].intent == 'RequestTopicInfo':
        return handleRequestTopicInfo(da_list)
        
    return da_list


gl_da_what_is_your_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(agent-name))')
gl_str_da_my_name_is = 'InformTD(self-name, Name($1))'

gl_da_what_is_my_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(user-name))')
gl_str_da_your_name_is = 'InformTD(partner-name, Name($1))'

gl_da_tell_me_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(telephone-number))')

gl_da_tell_you_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), InfoTopic(telephone-number))')

gl_da_affirmation_okay = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-okay)')
gl_da_affirmation_yes = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-yes)')
gl_da_self_ready = rp.parseDialogActFromString('InformDialogManagement(self-readiness)')
gl_da_self_not_ready = rp.parseDialogActFromString('InformDialogManagement(self-not-readiness)')



def handleRequestTopicInfo(da_list):
    da_request_topic_info = da_list[0]

    #handle 'User: what is your name'
    mapping = rp.recursivelyMapDialogRule(gl_da_what_is_your_name, da_request_topic_info)
    if mapping != None:
        str_da_my_name_is = gl_str_da_my_name_is.replace('$1', gl_agent.name)
        da_my_name_is = rp.parseDialogActFromString(str_da_my_name_is)
        return [da_my_name_is]

    #handle 'User: what is my name'
    mapping = rp.recursivelyMapDialogRule(gl_da_what_is_my_name, da_request_topic_info)
    if mapping != None:
        str_da_your_name_is = gl_str_da_your_name_is.replace('$1', gl_agent.partner_name)
        da_your_name_is = rp.parseDialogActFromString(str_da_your_name_is)
        return [da_your_name_is]

    #handle 'User: send me the phone number'
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_phone_number, da_request_topic_info)
    if mapping != None:
        gl_agent.setRole('send', gl_default_phone_number)
        #it would be best to spawn another thread to wait a beat then start the
        #data transmission process, but return okay immediately.
        #do that later
        initializeStatesToSendPhoneNumberData(gl_agent)
        sendNextDataChunk(gl_agent)
        #return [gl_da_affirmation_okay]

    #handle 'User: take this phone number'
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_you_phone_number, da_request_topic_info)
    if mapping != None:
        gl_agent.setRole('receive')
        return [gl_da_affirmation_okay, gl_da_self_ready]


    print 'no handler for request ' + da_request_topic_info.getPrintString()
    return da_list;




def initializeStatesToSendPhoneNumberData(agent):
    #agent is ready
    agent.self_dialog_model.readiness.setBeliefInTrue(1) 
    #agent believes partner is ready
    agent.partner_dialog_model.readiness.setBeliefInTrue(1) 

    #agent believes it is his turn
    agent.self_dialog_model.turn.setBeliefInTrue(.9) 
    #agent believes partner believes it is the agent's turn
    agent.partner_dialog_model.turn.setBeliefInTrue(.1) 

    #initialize agent starting at the first digit
    agent.self_dialog_model.data_index_pointer.initAllConfidenceInOne([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 0)   
    #agent believes the partner is also starting at the first digit
    agent.partner_dialog_model.data_index_pointer.initAllConfidenceInOne([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 0)   

    #initialize with chunk size 3
    agent.self_dialog_model.dm.protocol_chunk_size.initAllConfidenceInOne([1, 2, 3, 10], 3)     
    #agent believes the partner is ready for chunk size 3
    agent.partner_dialog_model.dm.protocol_chunk_size.initAllConfidenceInOne([1, 2, 3, 10], 3)     

    #initialize with moderate handshaking
    agent.self_dialog_model.dm.protocol_handshaking.initAllConfidenceInOne([1, 2, 3, 4, 5], 3)  
    #agent believes the partner is ready for moderate handshaking
    agent.partner_dialog_model.dm.protocol_handshaking.initAllConfidenceInOne([1, 2, 3, 4, 5], 3)  




def sendNextDataChunk(agent):
    consensus_index_pointer = agent.getConsensusIndexPointer()
    if consensus_index_pointer == None:
        return dealWithMisalignedIndexPointer()

    digit_lf_sequence = []
    chunk_size = agent.self_dialog_model.chunk_size.getDominantValue()

    last_index_to_send = consensus_index_pointer + chunk_size
    digit_sequence_lf = 'InformTD(ItemValue(DigitSequence('

    total_num_digits = len(agent.self_dialog_model.data_model.data_beliefs)
    for digit_i in range(consensus_index_pointer, min(last_index_to_send+1, total_num_digits)):
        digit_belief = agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value = digit_belief.getHighestConfidenceValue()  #a number string, e.g. 'one'
        digit_sequence_lf += data_value + ','
        
    #strip off the last comma
    digit_sequence_lf = digit_sequence_lf[:len(digit_sequence_lf-1)]
    digit_sequence_lf += ')))'

    #$$XX here advance the index pointer for the agent and the belief for the partner

    return digit_sequence_lf

        
        
        

def testDataAgreement(agent):
    return None
    

                        

#
#
###############################################################################



###############################################################################
#
#archives
#
