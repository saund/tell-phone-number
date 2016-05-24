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
#gl_turn_history = []   defined below
    
#Reset state by creating a new agent and clearing the turn history.
#Test the rules in gl_default_lf_rule_filename.
#Loop one input and print out the set of DialogActs interpreted
def loopDialog():
    global gl_agent
    global gl_turn_history
    gl_agent = createBasicAgent()
    gl_turn_history = []  
    rp.initLFRulesIfNecessary()

    #rp.setTell(True)

    da_issue_dialog_invitation = issueDialogInvitation()
    da_generated_word_list = rp.generateTextFromDialogAct(da_issue_dialog_invitation)
    print 'da_generated_word_list: ' + str(da_generated_word_list)
    if da_generated_word_list != None:
        str_generated = ' '.join(da_generated_word_list)
        print 'gen: ' + str_generated
    
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
        input_string = rp.removePunctuationAndLowerTextCasing(input_string)



#self_or_partner is 'self' or 'partner'
def fetchLastUtteranceFromTurnHistory(self_or_partner):
    global gl_turn_history
    for item_tup in gl_turn_history:
        if item_tup[0] == self_or_partner:
            return item_tup
    return None






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


#The semantics of a model of self and partner's beliefs, represented as distributions.
#
#self_dialog_model holds the self participant's belief in the data values and the dialog parameters.
#Is this a distribution?  Could be, if self is uncertain about the data values.
#
#partner dialog model has a confounding of possible interpretations.
#Is it, 
#  A. self's belief distribution about what partner holds as categorical values?
#  B. self's certain assertion of knowledge of what belief distribution partner holds?
#  C. self's belief distribution about what partner holds as a distribution over values?
#     In this case, it's a distribution of distributions.
#
#There is a fundamental difference in belief about facts and belief about aspects of
#dialog status that are socially negotiated.
#
#The values of digits are objective facts.  
#For the party holding the digit values, each digit's value is categorical, not a distribution.
#For the receiving party if the digit values are a distribution, then we'll have to use
#interpretations B or C.   Maybe with C, the distribution of distributions can be collapased
#into a single distribution.
#Alternatively, we can assume the receiver has a categorical belief in each digit value
#(which could be 'unknown').  
#Then, interpretation A comes into play. The distribution is self's distribution of 
#belief over which categorical value of digit value partner holds.
#Uncertainty will lead A to call for confirmation.
#
#Objective values are subject to belief recursion: "I believe that you believe that...".
#But even in the more complex case of C, there is always some grounded belief distrubution 
#across data values.
#
#By contrast, index pointer and turn are socially negotiated.
#Socially negotiated values are espcially difficult to disentagle from belief recursion 
#because there is no grounding in data values.  The only objective grounding is what was
#physically said.  But what was physically said is not what people care about. What they
#care about was the meaning of what was said, which is a reference to belief states.
#But this is itself subject to interpretation--and to differing 
#interpretations of the meanings inferred by eacy party.   So instead of recusion built
#from solid ground, we have recursion in a swirl of interpretations of interpretations.
#
#You get situations like,
#"You said X which I interpreted as X' but then I said Y and I thought you agreed to Y"
#
#Maybe this is the solution.  For socially negotiated properties, we *pretend* that there
#is an objective value written down somewhere.  Each party maintains its belief in what
#that value is, based on all past interaction.  That belief is a distribution over
#possible values of the objective value.  
#For turn, the value options might be  self / either / partner
#so the distribution is a multinomial.  During active conversation, the model
#might be that the objective value assigns turn to 'self' or 'partner' (but not 'either'),
#and that each participant estimates what the relative distribution is between
#them.  With wait time, the estimate slides toward oneseself, i.e. self's belief slides
#toward it believing it is self's turn, partner belief slides toward believing
#it is partner's turn.  So eventually someone is prompted to speak.
#Whereas, when the data exchange has concluded, then turn belief sloshes 
#into 'either'
#
#With data index pointer, the pretend objective value is the index of the digit or other
#data value being communicated.  Between communication of data values, this property's 
#value can linger around to reflect expectation of what data index's value will be 
#communicated next.



class DialogAgent():
    def __init__(self):
        self.name = None
        self.partner_name = None
        #for now, role serves as goal/activity status
        self.send_receive_role = 'banter'     #'send' or 'receive' or 'banter'
        self.self_dialog_model = None
        self.partner_dialog_model = None

    #If the role is send, then the DialogAgent will be initialized with a send_phone_number which will
    #be stuffed into the self_dialog_model.  The DialogAgent will be initialized believing that the 
    #recipient has no information about the phone number.
    #If the role is receive, then the send_phone_number will be None and the communction partner 
    #will be responsible for obtaining the phone number they speak to the DialogAgent, 
    #and the DialogAgent will start off with no information about the phone number.
    def setRole(self, send_or_receive, send_phone_number=None):
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

    def getConsensusIndexPointer(self, tell=False):
        self_dom_value = self.self_dialog_model.data_index_pointer.getDominantValue()
        partner_dom_value = self.partner_dialog_model.data_index_pointer.getDominantValue()
        if tell:
            print 'getConsensusIndexPointer  self: ' + str(self_dom_value) + ' partner: ' + str(partner_dom_value)
        if self_dom_value == partner_dom_value:
            return self_dom_value
        else:
            return None


    

#There will be one DialogModel for owner=self and one for owner=other-speaker
class DialogModel():
    def __init__(self):
        self.model_for = None       #one of 'self', 'partner'
        
        #for this application...
        self.data_model = None                   #A DataModel_USPhoneNumber
        self.data_index_pointer = None           #An OrderedMultinomialBelief: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
                                                 #data_index_pointer is self's belief about which data item is being referred to.
                                                 #Ontologically, we use the "pretend objective" strategy, where we pretend that
                                                 #there is an objective state of data_index_pointer, and the distribution is over
                                                 #beliefs in the value of that state on the part of self and partner.
                                                 #For an agent's self_dialog_model, index_pointer is used to look up data values to send,
                                                 #normally when agent's partner_dialog_model's index_pointer is in agreement.
                                                 #For an agent's partner_dialog_model, index_pointer can indicate either of two things:
                                                 #  -1. which digit the partner is referring to when they confirm data values
                                                 #  -2. which digit the partner is expecting to receive when self sends more data
                            

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



gl_default_phone_number = '6506371212'

def initSendReceiveDataDialogModel(self_or_partner, send_or_receive, send_phone_number=None):
    global gl_default_phone_number
    dm = DialogModel()
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    if send_or_receive == 'send' and send_phone_number != None:
        dm.data_model.setPhoneNumber(send_phone_number)
    dm.data_index_pointer = OrderedMultinomialBelief()
    dm.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, 0)   #initialize starting at the first digit
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = OrderedMultinomialBelief()
    dm.turn.setAllConfidenceInOne(gl_turn_mnb, 'either')                #will get overridden
    dm.protocol_chunk_size = OrderedMultinomialBelief()
    #dm.protocol_chunk_size.setAllConfidenceInOne([1, 2, 3, 4, 10], 3)     #initialize with chunk size 3/4 
    dm.protocol_chunk_size.setAllConfidenceInTwo([1, 2, 3, 4, 10], 3, 4)     #initialize with chunk size 3/4 
    dm.protocol_handshaking = OrderedMultinomialBelief()
    dm.protocol_handshaking.setAllConfidenceInOne([1, 2, 3, 4, 5], 3)  #initialize with moderate handshaking
    return dm


def initBanterDialogModel(self_or_partner):
    global gl_default_phone_number
    dm = DialogModel()
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    dm.data_index_pointer = OrderedMultinomialBelief()
    dm.data_index_pointer.setEquallyDistributed(gl_10_digit_index_list)   #no index pointer
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = OrderedMultinomialBelief()
    dm.turn.setAllConfidenceInOne(gl_turn_mnb, 'either')
    dm.protocol_chunk_size = OrderedMultinomialBelief()
    dm.protocol_chunk_size.setAllConfidenceInTwo([1, 2, 3, 4, 10], 3, 4)     #initialize with chunk size 3/4 
    dm.protocol_handshaking = OrderedMultinomialBelief()
    dm.protocol_handshaking.setAllConfidenceInOne([1, 2, 3, 4, 5], 3)  #initialize with moderate handshaking
    return dm



        



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
        #data segments, [start_index, end_index] inclusive
        self.data_indices = {'area-code':[0,2],\
                             'prefix':[3,5],\
                             'last-four-digits':[6,9]}


    #phone_number_string is like '3452233487', i.e. ten digits in a row
    def setPhoneNumber(self, phone_number_string):
        if phone_number_string != None and len(phone_number_string) != 10:
            print 'setPhoneNumber got a phone_number_string: ' + phone_number_string + ' that is not 10 digits long'
            return
        for i in range(0, 10):
            numerical_digit = phone_number_string[i]
            word_digit = numericalDigitToWordDigit(numerical_digit)
            self.data_beliefs[i].setValueDefinite(word_digit)


    #digit_value is a string
    def setNthPhoneNumberDigit(self, nth, digit_value):
        self.data_beliefs[nth].setValueDefinite(digit_value)

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




#For telephone number communication, the Banter data model will hold conversation
#context state about
# -user and agent goals and intentions
#  (user or agent intent to send or receive a phone number)
# -agent competency
# -hanging questions (e.g. do you want to send or receive a phone number?)
# -maybe something about the various phone numbers the agent knows, to
#  enrich the selection. Make it more like a directory.
class DataModel_Banter(DataModel):
    def __init__(self):
        self.type = 'banter'
        self.current_topic = None

    def getPrintString(self):
        pstr = 'DataModel_Banter is not finished'
        return pstr

    def getPrintStringAbbrev(self):
        pstr = 'DataModel_Banter is not finished'
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

    def setEquallyDistributed(self, value_list):
        self.value_name_confidence_list = []
        conf = 1.0 / len(value_list)
        for i in range(0, len(value_list)):
            self.value_name_confidence_list.append([value_list[i], conf])

    def setAllConfidenceInOne(self, value_list, all_confidence_value):
        self.value_name_confidence_list = []
        for i in range(0, len(value_list)):
            this_value = value_list[i]
            if this_value == all_confidence_value:
                conf = 1.0
            else:
                conf = 0.0
            self.value_name_confidence_list.append([this_value, conf])

    def setAllConfidenceInTwo(self, value_list, half_confidence_value_1, half_confidence_value_2):
        self.value_name_confidence_list = []
        for i in range(0, len(value_list)):
            this_value = value_list[i]
            if this_value == half_confidence_value_1 or this_value == half_confidence_value_2:
                conf = .5
            else:
                conf = 0.0
            self.value_name_confidence_list.append([this_value, conf])


    #returns -1 if the dominant value is out of range
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

    #returns a tuple of tuples ((max_value, max_conf), (second_max_value, second_max_conf))
    def getTwoMostDominantValues(self):
        max_conf = 0.0
        max_value = -1
        second_max_conf = 0.0
        second_max_value = 0.0
        for i in range(0, len(self.value_name_confidence_list)):
            value_name_confidence = self.value_name_confidence_list[i]
            value = value_name_confidence[0]
            confidence = value_name_confidence[1]
            if confidence > max_conf:
                second_max_value = max_value
                second_max_conf = max_conf
                max_conf = confidence
                max_value = value
            elif confidence > second_max_conf:
                second_max_value = value
                second_max_conf = confidence
        ret = ((max_value, max_conf), (second_max_value, second_max_conf))
        return ret

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


gl_number_to_word_map = {'1':'one', '2':'two', '3':'three', '4':'four', '5':'five',\
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

#each turn is a tuple: (speaker = 'self' or 'partner', DialogAct list, utterance word tuple)
#DialogAct list is a list of DialogAct instances, not their string versions
#for now we may not be including the utterance word tuple because that has to be gotten from the ruleProcessing side
#Each new turn is prepended to the front of the list so the most recent turn is [0]
gl_turn_history = []



def generateResponseToInputDialog(user_da_list):
    global gl_turn_history

    if len(user_da_list) == 0:
        print 'what? user_da_list length is 0'
        return user_da_list

    gl_turn_history.insert(0, ('partner', user_da_list))
    da_response = None

    if user_da_list[0].intent == 'InformTopicInfo':
        da_response = handleInformTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'InformDialogManagement':
        da_response = handleInformDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'RequestTopicInfo':
        da_response = handleRequestTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'RequestDialogManagement':
        da_response = handleRequestDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'CheckTopicInfo':
        da_response = handleCheckTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'CheckDialogManagement':
        da_response = handleCheckDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'ConfirmTopicInfo':
        da_response = handleConfirmTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'ConfirmDialogManagement':
        da_response = handleConfirmDialogManagement(user_da_list)
    elif user_da_list[0].intent == 'CorrectionTopicInfo':
        da_response = handleCorrectionTopicInfo(user_da_list)
    elif user_da_list[0].intent == 'CorrectionDialogManagement':
        da_response = handleCorrectionDialogManagement(user_da_list)

    
    if da_response != None:
        gl_turn_history.insert(0, ('self', da_response))
    else:
        print '!Did not generate a response to user input DialogActs:'
        for user_da in user_da_list:
            user_da.printSelf()
        da_response = []
        
    return da_response


gl_da_inform_dm_greeting = rp.parseDialogActFromString('InformDialogManagement(greeting)')
gl_str_da_inform_dm_greeting = 'InformDialogManagement(greeting)'

gl_da_what_is_your_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(agent-name))')
gl_str_da_my_name_is = 'InformTopicInfo(self-name, Name($1))'

gl_da_what_is_my_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(user-name))')
gl_str_da_your_name_is = 'InformTopicInfo(partner-name, Name($1))'

gl_da_tell_me_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(telephone-number))')
gl_da_tell_you_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), InfoTopic(telephone-number))')

gl_da_tell_me_topic_info = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic($1))')
gl_da_tell_you_topic_info = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), InfoTopic($1))')

gl_da_request_topic_info = rp.parseDialogActFromString('RequestTopicInfo(ItemType($1))')
gl_str_request_topic_info = 'RequestTopicInfo(ItemType($1))'

gl_da_say_item_type = rp.parseDialogActFromString('InformTopicInfo(SayItemType($1))')
gl_str_da_say_item_type = 'InformTopicInfo(SayItemType($1))'


gl_da_affirmation_okay = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-okay)')
gl_da_affirmation_yes = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-yes)')
gl_da_affirmation = rp.parseDialogActFromString('ConfirmDialogManagement($1)')


gl_da_self_ready = rp.parseDialogActFromString('InformDialogManagement(self-readiness)')
gl_da_self_not_ready = rp.parseDialogActFromString('InformDialogManagement(self-not-readiness)')
gl_da_all_done = rp.parseDialogActFromString('InformTopicInfo(all-done)')

gl_da_what = rp.parseDialogActFromString('RequestDialogManagement(what)')
gl_str_da_what = 'RequestDialogManagement(what)'

gl_misalignment_self_hearing_or_understanding = rp.parseDialogActFromString('RequestDialogManagement(misalignment-self-hearing-or-understanding)')
gl_str_misalignment_self_hearing_or_understanding = 'RequestDialogManagement(misalignment-self-hearing-or-understanding)'

gl_misalignment_self_hearing_or_understanding_pronoun_ref = rp.parseDialogActFromString('RequestDialogManagement(misalignment-self-hearing-or-understanding, pronoun_ref)')
gl_str_misalignment_self_hearing_or_understanding_pronoun_ref = 'RequestDialogManagement(misalignment-self-hearing-or-understanding, pronoun_ref)'

gl_misalignment_self_hearing_or_understanding_item_type = rp.parseDialogActFromString('RequestDialogManagement(misalignment-self-hearing-or-understanding, ItemType($1))')
gl_str_misalignment_self_hearing_or_understanding_item_type = 'RequestDialogManagement(misalignment-self-hearing-or-understanding, ItemType($1))'

gl_misalignment_request_repeat = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat)')
gl_str_misalignment_request_repeat = 'RequestDialogManagement(misalignment-request-repeat)'

gl_inform_dm_repeat_intention = rp.parseDialogActFromString('InformDialogManagement(repeat-intention)')
gl_str_inform_dm_repeat_intention = 'InformDialogManagement(repeat-intention)'

gl_correction_topic_info = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction)')
gl_str_correction_topic_info = 'CorrectionTopicInfo(partner-correction)'



#gg


####
#
#Inform
#
#Proffer information about topic or dialog management.
#Assumption that the recipient's belief confidence is low.
#



#InformTopicInfo
#Proffer information about topic

#Because template rule interpretation does not support return of mutliple intents for
#the same words, InformTopicInfo has to do double duty with CheckTopicInfo.
#This is done by assuming that if self role is sending, then receipt of an InformTopicInfo
#DialogAct from partner is actually a CheckTopicInfo.
#CheckTopicInfo occurs when the information receiver has high confidence and is 
#reiterating data values for the purpose of confirmation.
#
#
def handleInformTopicInfo(da_list):
    if gl_agent.send_receive_role == 'send':
        return handleInformTopicInfo_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleInformTopicInfo_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        return handleInformTopicInfo_BanterRole(da_list)


#For agent send role, handle InformTopicInfo of the following kinds
#(DialogActs coming from information recipient partner):
#  - partner check-confirming digit values only (CheckTopicInfo)
#    In this case, agent surmises that the partner's belief in the index pointer has advanced
#    It is possible the partner could submit digit values that are not correct reiteration
#    of the chunck just sent, but align with a different part of the number, e.g. self
#    issuing an area code and partner responding with the correct prefix.  So this function 
#    has to make an inference about partner index pointer for the check data values received.
#  - partner check-confirming digit values mixed with an indication of misunderstanding, e.g. what?
#    In this case, agent surmises that the partner's belief in the index pointer has not advanced.
#  
#
#XBut sometimes the partner's index pointer belief model cannot be resolved in this turn.
#XThey might issue a digit confirmation tentatively, and it doesn't get resolved until 
#Xself issues a confirmation back. E.g.
#X
#Xself:      six two three
#Xpartner:   six two three     -> tentative advance of partner index pointer
#Xself:      right             -> accept partner index pointer advance 
#X
#Xself:      six two three
#Xpartner:   six two four?     -> tentative advance of partner index pointer
#Xself:      no                -> reject advance of partner index pointer
#X
#Xself:      six two three
#Xpartner:   six two three    -> tentative advance of partner index pointer
#Xself:      four five one    -> accept advance of partner index pointer, partner has 
#X                               implicitly received approval of their tentative advance
#
#These are InformTopicInfo because we are not currently able to parse input as multiple
#candidate DialogActs with different intents.
def handleInformTopicInfo_SendRole(da_list):
    global gl_agent
        
    #This is our belief in what the partner's index pointer is.
    #This will be updated based on the partner DialogActs' indications that the partner has
    #advanced the index pointer or not.  In other words, do they indicate that 
    #they are confused, and hence maintain the pointer at the beginning or within the
    #last data chucnk,
    #or do they indicate confidence in their digits received (which may be incorrect)
    #and hence have advanced the pointer to the next chunk?
    #tentative_partner_index_pointer = gl_agent.partner_dialog_model.data_index_pointer.getDominantValue()

    partner_digit_word_sequence = []

    #maintain this flag as check digits from the partner are processed under the expectation of reiterating
    #the last sent chunk.  If this flag ends up getting set to false because something other than repeat check
    #was said, then we'll have to do something else.
    check_matches_last_chunk_p = True
    partner_expresses_confusion_p = False

    temp_digit_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()

    #could be an interspersing of ItemValue(Digit( and ItemValue(DigitSequence
    for da in da_list:
        str_da_inform_td = da.getPrintString()
        if str_da_inform_td.find('InformTopicInfo(ItemValue(Digit(') == 0:
            start_index = len('InformTopicInfo(ItemValue(Digit(')
            rp_index = str_da_inform_td.find(')', start_index)
            partner_check_digit_value = str_da_inform_td[start_index:rp_index]
            partner_digit_word_sequence.append(partner_check_digit_value)
            
            digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[temp_digit_index_pointer]
            data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            correct_digit_value = data_value_tuple[0]
            if partner_check_digit_value == correct_digit_value:
                temp_digit_index_pointer += 1
            else:
                check_matches_last_chunk_p = False

        elif str_da_inform_td.find('InformTopicInfo(ItemValue(DigitSequence(') == 0:
            start_index = len('InformTopicInfo(ItemValue(DigitSequence(')
            rp_index = str_da_inform_td.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(str_da_inform_td[start_index:rp_index])
            partner_digit_word_sequence.extend(digit_value_list)
            for partner_check_digit_value in digit_value_list:
                digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[temp_digit_index_pointer]
                data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
                correct_digit_value = data_value_tuple[0]
                if partner_check_digit_value == correct_digit_value:
                    temp_digit_index_pointer += 1
                else:
                    check_matches_last_chunk_p = False

        elif str_da_inform_td == gl_str_da_what:
            #partner indicates confusion so we surmise they have not advanced their index pointer with this data chunk.
            #So reset the tentative_partner_index_pointer.
            temp_digit_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()
            partner_expresses_confusion_p = True

            
    if partner_expresses_confusion_p:

        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret = [gl_inform_dm_repeat_intention]
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret

    elif check_matches_last_chunk_p == False:
        ret = [gl_correction_topic_info]
        #Since there was no advance, this will send the last data chunk again.
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret

    #all good, we have received from the partner a correct check of the last chunk of digits sent
    else:
            
        pointer_advance_count = updateBeliefInPartnerDataStateForDigitValueList(partner_digit_word_sequence)
        middle_or_at_end = advanceSelfIndexPointer(gl_agent, pointer_advance_count)  
        (self_belief_partner_is_wrong_digit_indices, self_believes_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

        if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
                len(self_believes_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return [gl_da_all_done];

        else:
            return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()

        #return prepareNextDataChunk(gl_agent)
    




def handleInformTopicInfo_ReceiveRole(da_list):
    print 'handleInformTopicInfo_ReceiveRole not written yet'
    return None


def handleInformTopicInfo_BanterRole(da_list):
    
    print 'handleInformTopicInfo_BanterRole not written yet'
    return None




#InformDialogManagement
#Proffer information about dialog management
#
def handleInformDialogManagement(da_list):


    if gl_agent.send_receive_role == 'send':
        return handleInformTopicInfo_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleInformTopicInfo_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        da0 = da_list[0]
        str_da0 = da0.getPrintString()
        print 'str_da0: ' + str_da0
        if str_da0 == gl_str_da_inform_dm_greeting:
            return [gl_da_inform_dm_greeting, gl_da_dialog_invitation]
    




#should have something here about partner indicating readiness




####
#
#Request
#
#Request information about topic or dialog management,
#or request adjustment in dialog management protocol.
#Assumption that the speaker's belief confidence is low.
#


#RequestTopicInfo
#Request information about topic
#
def handleRequestTopicInfo(da_list):
    da_request_topic_info = da_list[0]

    print 'handleRequestTopicInfo da_list: '
    for da in da_list:
        da.printSelf()

    #handle 'User: what is your name'
    #rp.setTellMap(True)
    mapping = rp.recursivelyMapDialogRule(gl_da_what_is_your_name, da_request_topic_info)
    #print 'mapping: ' + str(mapping)
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

    #This is probably superfluous, covered by the tell me the X? below.
    #handle 'User: send me the phone number'
    #rp.setTellMap(True)
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_me_phone_number, da_request_topic_info)
    #print 'mapping: ' + str(mapping)
    if mapping != None:
        gl_agent.setRole('send', gl_default_phone_number)
        #it would be best to spawn another thread to wait a beat then start the
        #data transmission process, but return okay immediately.
        #do that later
        initializeStatesToSendPhoneNumberData(gl_agent)
        return prepareNextDataChunk(gl_agent)
        #return [gl_da_affirmation_okay]

    #handle 'User: tell me the X?
    mapping_tell_me = rp.recursivelyMapDialogRule(gl_da_tell_me_topic_info, da_request_topic_info)
    #handle 'User: what is the X?
    mapping_what_is = rp.recursivelyMapDialogRule(gl_da_request_topic_info, da_request_topic_info)

    if mapping_tell_me != None:
        mapping = mapping_tell_me
    if mapping_what_is != None:
        mapping = mapping_what_is

    if mapping != None:
        print 'mapping: ' + str(mapping)
        if mapping.get('1') == 'telephone-number':
            gl_agent.setRole('send', gl_default_phone_number)
            initializeStatesToSendPhoneNumberData(gl_agent)
            return prepareNextDataChunk(gl_agent)
        #handle 'User: what is the area code', etc.
        elif mapping.get('1') in gl_agent.self_dialog_model.data_model.data_indices.keys():
            segment_chunk_name = mapping.get('1')
            if gl_agent.send_receive_role == 'send':
                return handleSendSegmentChunkNameAndData(segment_chunk_name)

#            if gl_agent.send_receive_role == 'send':
#                chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(send_chunk_name)
#                #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
#                for data_index_pointer in chunk_indices:
#                    gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?')
#                chunk_start_index = chunk_indices[0]
#                gl_agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, chunk_start_index)
#                gl_agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, chunk_start_index)
#                str_da_say_item_type = gl_str_da_say_item_type.replace('$1', send_chunk_name)
#                da_say_item_type = rp.parseDialogActFromString(str_da_say_item_type)
#                #print 'str_da_say_item_type: ' + str_da_say_item_type
#                #print 'da_say_item_type: ' + da_say_item_type.getPrintString()
#                ret = [da_say_item_type]
#                ret.extend(prepareNextDataChunk(gl_agent))
#                #print 'ret: ' + str(ret)
#                return ret
    #handle 'User: take this phone number'
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_you_phone_number, da_request_topic_info)
    if mapping != None:
        gl_agent.setRole('receive')
        return [gl_da_affirmation_okay, gl_da_self_ready]


    print 'handleRequestTopicInfo has no handler for request ' + da_request_topic_info.getPrintString()
    return da_list;



#RequestDialogManagement
#Request information about dialog management, or request adjustment in dialog management protocol.
#
def handleRequestDialogManagement(da_list):
    da_request_dm = da_list[0] 
    str_da_request_dm = da_request_dm.getPrintString()

    #print 'handleRequestDialogManagement()'
    #for da in da_list:
    #    da.printSelf()
    #handle "i didn't get that"
    #print 'str_da_request_dm: ' + str_da_request_dm
    #print 'gl_str_misalignment_self_hearing_or_understanding_pronoun_ref: ' + gl_str_misalignment_self_hearing_or_understanding_pronoun_ref
    if str_da_request_dm == gl_str_misalignment_self_hearing_or_understanding_pronoun_ref:
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        if last_self_utterance_tup != None:
            return last_self_utterance_tup[1]
    #handle "repeat that"
    if str_da_request_dm == gl_str_misalignment_request_repeat:
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        if last_self_utterance_tup != None:
            #print 'last_self_utterance_tup: ' + str(last_self_utterance_tup)
            return last_self_utterance_tup[1]

    print 'str_da_request_dm: ' + str_da_request_dm
    print 'gl_misalignment_self_hearing_or_understanding_item_type: ' + gl_misalignment_self_hearing_or_understanding_item_type.getPrintString()
    mapping = rp.recursivelyMapDialogRule(gl_misalignment_self_hearing_or_understanding_item_type, da_request_dm)
    if mapping != None:
        misunderstood_item_type = mapping.get('1')
        if misunderstood_item_type in gl_agent.self_dialog_model.data_model.data_indices.keys():
            return handleSendSegmentChunkNameAndData(misunderstood_item_type)

    



def handleSendSegmentChunkNameAndData(segment_chunk_name):
    chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_chunk_name)
    #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
    for data_index_pointer in chunk_indices:
        gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?')
        chunk_start_index = chunk_indices[0]
        gl_agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, chunk_start_index)
        gl_agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, chunk_start_index)
        str_da_say_item_type = gl_str_da_say_item_type.replace('$1', segment_chunk_name)
        da_say_item_type = rp.parseDialogActFromString(str_da_say_item_type)
        ret = [da_say_item_type]
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret



####
#
#Check
#
#Reiterate or request affirmation of topic information or dialog management protocol state.
#Assumption that the speaker's belief confidence is high.
#


#CheckTopicInfo
#Reiterate or solicit affirmation of topic information.
#
def handleCheckTopicInfo(da_list):
    print 'handleCheckTopicInfo not written yet'



#CheckDialogManagement
#Solicit request of affirmation of dialog management parameters and status.
#
def handleCheckDialogManagement(da_list):
    print 'handleCheckDialogManagement not written yet'


####
#
#Confirm
#
#Profide confirmation or affirmation of topic information or dialog management.
#Assumption that the speaker's belief confidence is high.
#Used if sender believes the recipient's information is correct.
#

#ConfirmTopicInfo
#Reiterate or affirm/disaffirm topic information.
#ConfirmTopicInfo will be used almost exclusively by the information sender.
#
def handleConfirmTopicInfo(da_list):
    print 'handleConfirmTopicInfo not written yet'



#ConfirmDialogManagement
#Reiterate or affirm/disaffirm dialog management protocol state.
#
#This needs to take into account self role
#Now written only for 'send'
def handleConfirmDialogManagement(da_list):
    da_confirm_dm = da_list[0]

    #handle affirmation continuer: 'User: okay or User: yes
    mapping = rp.recursivelyMapDialogRule(gl_da_affirmation, da_confirm_dm)
    if mapping == None:
        return

    if gl_agent.send_receive_role == 'banter':
        return [dealWithMisalignedRoles(), issueDialogInvitation()]

    if gl_agent.send_receive_role == 'send':

        pointer_advance_count = updateBeliefInPartnerDataStateBasedOnLastDataSent()  #advances the partner's index pointer
        middle_or_at_end = advanceSelfIndexPointer(gl_agent, pointer_advance_count)  
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

        if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
                len(self_belief_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return [gl_da_all_done];

        return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()




#Compares self and partner data_model beliefs, and prepares a next set of DialogActs to send.
#Under a normal send situation, the delta in data_model beliefs will be the partner holding unknown (?)
#data values for the next segment, as indicateb by the consensus index pointer.
#If this is the case, then just the data of the next segment are queued up as DialogActs.
#If however partner's data_model has a high confidence conflict with self's, or if the 
#first unknown digit is not the start of the next consensus index pointer segment, then
#this prepares a sequence of DialogActs that calls out the segment name explicitly.
def prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers():
    global gl_agent
    (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

    print 'prepareAndSentNext... self data_index_pointer: ' +\
        str(gl_agent.self_dialog_model.data_index_pointer.getDominantValue()) +\
        ' partner data_index_pointer: ' + str(gl_agent.partner_dialog_model.data_index_pointer.getDominantValue())
    print 'self_belief_partner_is_wrong_digit_indices: ' + str(self_belief_partner_is_wrong_digit_indices)
    print 'self_belief_partner_registers_unknown_digit_indices: ' + str(self_belief_partner_registers_unknown_digit_indices)

    
    consensus_index_pointer = gl_agent.getConsensusIndexPointer()
    data_index_of_focus = None

    #Assume the unknown digits are in small-to-large order.
    if len(self_belief_partner_is_wrong_digit_indices) > 0:
        data_index_of_focus = self_belief_partner_is_wrong_digit_indices[0]

    #Assume the unknown digits are in small-to-large order.
    if len(self_belief_partner_registers_unknown_digit_indices) > 0:
        data_index_of_focus = self_belief_partner_registers_unknown_digit_indices[0]

    #we're done actually
    if data_index_of_focus == None:
        gl_agent.setRole('banter')
        return [gl_da_all_done];

    print 'data_index_of_focus: ' + str(data_index_of_focus)

    #Most of the time, this will just hit on the next chunk of digits to send...
    if consensus_index_pointer != None and consensus_index_pointer == data_index_of_focus:
        return prepareNextDataChunk(gl_agent)

    #If we drop through to here, then say explicitly what chunk segment we're delivering next
    (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(data_index_of_focus)
    gl_agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, segment_start_index)
    gl_agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, segment_start_index)
    str_da_say_item_type = gl_str_da_say_item_type.replace('$1', segment_name)
    da_say_item_type = rp.parseDialogActFromString(str_da_say_item_type)
    ret = [da_say_item_type]
    ret.extend(prepareNextDataChunk(gl_agent))
    return ret





#Returns a tuple (segment_name, start_index_pointer, chunk_size) for the data_pointer_index 
#value passed based on the agent's data_model.  The data_index_pointer passed could be in the
#middle of a chunk.
def findSegmentNameAndChunkSizeForDataIndex(data_index_pointer):
    global gl_agent
    for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]
        if data_index_pointer < segment_start_index:
            continue
        elif data_index_pointer > segment_end_index:
            continue
        else:
            chunk_size = segment_end_index - segment_start_index + 1
            return (segment_name, segment_start_index, chunk_size)





####
#
#Correction
#
#Disaffirm topic information as communicated or dialog management protocol state.
#Assumption that that the recipient's belief confidence is high.
#Used if sender believes the recipient's information is incorrect.
#

#CorectionTopicInfo
#Reiterate or affirm/disaffirm topic information.
#
def handleCorrectionTopicInfo(da_list):
    print 'handleCorrectionTopicInfo not written yet'

#CorectionDialogManagement
#Reiterate or affirm/disaffirm topic information.
#
def handleCorrectionDialogManagement(da_list):
    print 'handleCorrectionDialogManagement not written yet'


#
####
#
#################




def initializeStatesToSendPhoneNumberData(agent):
    #agent is ready
    agent.self_dialog_model.readiness.setBeliefInTrue(1) 
    #agent believes partner is ready
    agent.partner_dialog_model.readiness.setBeliefInTrue(1) 

    #agent believes it is his turn
    agent.self_dialog_model.turn.setAllConfidenceInOne(gl_turn_mnb, 'self')
    #agent believes partner believes it is the agent's turn
    agent.partner_dialog_model.turn.setAllConfidenceInOne(gl_turn_mnb, 'self')

    #initialize agent starting at the first digit
    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, 0)   
    #agent believes the partner is also starting at the first digit
    agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, 0)   

    #initialize with chunk size 3/4
    #agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInOne([1, 2, 3, 4, 10], 3)
    agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInTwo([1, 2, 3, 4, 10], 3, 4)     
    #agent believes the partner is ready for chunk size 3/4
    #agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInOne([1, 2, 3, 4, 10], 3) 
    agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInTwo([1, 2, 3, 4, 10], 3, 4)     

    #initialize with moderate handshaking
    agent.self_dialog_model.protocol_handshaking.setAllConfidenceInOne([1, 2, 3, 4, 5], 3)  
    #agent believes the partner is ready for moderate handshaking
    agent.partner_dialog_model.protocol_handshaking.setAllConfidenceInOne([1, 2, 3, 4, 5], 3)  




def prepareNextDataChunk(agent):
    consensus_index_pointer = agent.getConsensusIndexPointer()
    if consensus_index_pointer == None:
        print 'prepareNextDataChunk encountered misaligned consensus_index_pointer, calling again with tell=True'
        agent.getConsensusIndexPointer(True)
        return [dealWithMisalignedIndexPointer()]

    if consensus_index_pointer >= 10:
        return [gl_da_all_done];


#    chunk_size = -1
#    #try to choose chunk size 3 for area code, 3, for prefix
#    pref_chunk_size_options = agent.self_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
#    if consensus_index_pointer == 0 or consensus_index_pointer == 3:
#        if pref_chunk_size_options[0][1] > .4 and pref_chunk_size_options[0][0] == 3 or\
#           pref_chunk_size_options[1][1] > .4 and pref_chunk_size_options[1][0] == 3:
#            chunk_size = 3
#    #try to choose chunk size 4 for last four digits
#    if consensus_index_pointer == 6:
#        if pref_chunk_size_options[0][1] > .4 and pref_chunk_size_options[0][0] == 4 or\
#           pref_chunk_size_options[1][1] > .4 and pref_chunk_size_options[1][0] == 4:
#            chunk_size = 4
#    if chunk_size == -1:
#        chunk_size = agent.self_dialog_model.protocol_chunk_size.getDominantValue()

    #choose chunk size to advance to the next segment boundary (area-code, prefix, last-four-digits)

    for segment_name in agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]
        if consensus_index_pointer < segment_start_index:
            continue
        elif consensus_index_pointer > segment_end_index:
            continue
        else:
            chunk_size = segment_end_index - consensus_index_pointer + 1
            break
        

    print 'chunk_size: ' + str(chunk_size) + ' consensus_index_pointer: ' + str(consensus_index_pointer) + ' segment_name: ' + segment_name

    data_value_list = []
    total_num_digits = len(agent.self_dialog_model.data_model.data_beliefs)
    last_index_to_send = consensus_index_pointer + chunk_size
    for digit_i in range(consensus_index_pointer, min(last_index_to_send, total_num_digits)):
        digit_belief = agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)
        
    if len(data_value_list) == 1:
        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(Digit(' + data_value_list[0] + ')))'
    else:
        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(DigitSequence('
        for data_value in data_value_list:
            str_digit_sequence_lf += data_value + ','

        #strip off the last comma
        str_digit_sequence_lf = str_digit_sequence_lf[:len(str_digit_sequence_lf)-1]
        str_digit_sequence_lf += ')))'
    
    digit_sequence_lf = rp.parseDialogActFromString(str_digit_sequence_lf)
    return [digit_sequence_lf]


####
#This is obsolete because it is too simplistic.
#This advances the index pointer belief of the agent's self and partner data models by chunk_size
#Instead, we only advance the belief in the partner index pointer when we believe they have received the data
#and it is correct.  The partner may have advanced their data index pointer, but if self believes they have
#gotten the information incorrect, then self may have to correct them.
#Only then do we advance the self index pointer.
#
def advanceIndexPointerBeliefs(agent):
    consensus_index_pointer = agent.getConsensusIndexPointer()
    if consensus_index_pointer == None:
        return [dealWithMisalignedIndexPointer()]

    if consensus_index_pointer >= 10:
        return [gl_da_all_done];

    chunk_size = agent.self_dialog_model.protocol_chunk_size.getDominantValue()

    next_data_index_pointer_loc = consensus_index_pointer + chunk_size

    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, next_data_index_pointer_loc)
    agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, next_data_index_pointer_loc)

    print 'adancing index pointer by chunk_size: ' + str(chunk_size) + ' to ' + str(consensus_index_pointer)
#
#####



gl_10_digit_index_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

#Turn is absolute, 'self' refers to the agent.self and 'partner' refers to agent.partner.
#This is the case both for agent.self_data_model and agent.partner_data_model
#So gl_turn_mnb will be [0, 0, 1] if partner thinks it is their turn.
gl_turn_mnb = ['self', 'either', 'partner']


#return 'middle' or 'at-end'
def advanceSelfIndexPointer(agent, pointer_advance_count):
    self_dm = agent.self_dialog_model
    self_index_pointer = self_dm.data_index_pointer.getDominantValue()

    #if self_index_pointer >= 9:
    #    return 'done-already'
    
    next_data_index_pointer_loc = self_index_pointer + pointer_advance_count
    if next_data_index_pointer_loc >= len(gl_10_digit_index_list):
        agent.self_dialog_model.data_index_pointer.setEquallyDistributed(gl_10_digit_index_list)
        return 'at-end'
        
    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, next_data_index_pointer_loc)
    print 'advancing index pointer by : ' + str(pointer_advance_count) + ' to ' + str(next_data_index_pointer_loc)
    return 'middle'








#simple version:
#retrieve data values sent in last single self turn,
#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#A more advanced version will consider the belief in the partner's expected chunk size, and 
#account for the fact that the partner may be confused if the number of digits sent does not
#match their expected chunk size.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnLastDataSent():
    global gl_turn_history
    last_self_data_sent = None
    for turn_i in range(0, len(gl_turn_history)):
        turn_tup = gl_turn_history[turn_i]
        if turn_tup[0] == 'partner':
            continue
        turn_da_list = turn_tup[1]
        turn_includes_InformTopicInfoItemValue = False
        for da in turn_da_list:
            da_print_string = da.getPrintString()
            if da_print_string.find('InformTopicInfo(ItemValue(') < 0:
                continue
            turn_includes_InformTopicInfoItemValue = True
            break
        if turn_includes_InformTopicInfoItemValue == True:
            last_self_data_sent = turn_da_list
            break
        else:
            print 'error updateBeliefInPartnerDataStateBasedOnLastDataSent() did not see any data DialogActs to base update on'
        
    if last_self_data_sent != None:
        return updateBeliefInPartnerDataStateBasedOnDataValues(last_self_data_sent)
    else:
        return 0
    

#da_list probably consists of a single DialogAct, either 
#  InformTopicInfo(ItemValue(Digit(x1)))  or else
#  InformTopicInfo(ItemValue(DigitSequence(x1, x2, x3)))  
#where x1 will be a string digit value, e.g. 'one'
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnDataValues(da_list):
    #print 'updateBeliefInPartnerDataStateBasedOnDataValues(da_list)'
    for da in da_list:
        da_print_string = da.getPrintString()
        #print 'da: ' + da_print_string
        
        ds_index = da_print_string.find('InformTopicInfo(ItemValue(DigitSequence(')
        if ds_index == 0:
            start_index = len('InformTopicInfo(ItemValue(DigitSequence(')
            rp_index = da_print_string.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(da_print_string[start_index:rp_index])
            print 'digit_value_list: ' + str(digit_value_list)
            return updateBeliefInPartnerDataStateForDigitValueList(digit_value_list)
        d_index = da_print_string.find('InformTopicInfo(ItemValue(Digit(')
        if d_index == 0:
            start_index = len('InformTopicInfo(ItemValue(Digit(')
            rp_index = da_print_string.find(')', start_index)
            digit_value = da_print_string[start_index:rp_index]
            return updateBeliefInPartnerDataStateForDigitValueList([digit_value])
        print 'error updateBeliefInPartnerDataStateBasedOnLastDataSent() was unable to identify digits to update'
        
    return 0
    


#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#str_digit_list is a list of strings, e.g. ['one', 'six'...]
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateForDigitValueList(str_digit_value_list):
    #print 'updateBeliefInPartnerDataStateForDigitList(' + str(str_digit_value_list) + ')'
    partner_dm = gl_agent.partner_dialog_model
    partner_index_pointer_advance_count = 0

    for digit_value in str_digit_value_list:
        partner_index_pointer_value = partner_dm.data_index_pointer.getDominantValue()
        partner_dm.data_model.setNthPhoneNumberDigit(partner_index_pointer_value, digit_value)
        partner_index_pointer_value += 1
        partner_index_pointer_advance_count += 1
        partner_dm.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, partner_index_pointer_value)

    return partner_index_pointer_advance_count


#This should be adjustable per requirements for correct transfer.
gl_threshold_on_belief_partner_has_wrong_value = .25



#Returns a tuple:  (list of data indices for which the confidence is high but the values disagree,
#                   list of data indices for which the recipient registers ?)
#                
def compareDataModelBeliefs():
    global gl_threshold_on_belief_partner_has_wrong_value
    digits_out_of_agreement = []
    digits_self_believes_partner_registers_unknown = []

    self_dm = gl_agent.self_dialog_model
    self_data_model_beliefs = gl_agent.self_dialog_model.data_model.data_beliefs  #a list of DigitBelief
    partner_dm = gl_agent.partner_dialog_model
    partner_data_model_beliefs = gl_agent.partner_dialog_model.data_model.data_beliefs  #a list of DigitBelief

    for i in range (0, len(self_data_model_beliefs)):
        self_digit_belief = self_data_model_beliefs[i]       #a DigitBelief
        self_belief_tup = self_digit_belief.getHighestConfidenceValue()   #a tuple e.g. ('one', .8)
        partner_digit_belief = partner_data_model_beliefs[i]
        partner_belief_tup = partner_digit_belief.getHighestConfidenceValue()   #a tuple e.g. ('one', .8)
        if self_belief_tup[0] == partner_belief_tup[0]:
            continue
        if partner_belief_tup[0] == '?':
            digits_self_believes_partner_registers_unknown.append(i)
            continue
        if partner_belief_tup[1] > threshold_on_belief_partner_has_wrong_value:
            print 'compareDataModelBeliefs: self: ' + str(self_belief_tup) + ' partner: ' + str(partner_belief_tup)
            digits_out_of_agreement.append(i)

    return (digits_out_of_agreement, digits_self_believes_partner_registers_unknown)




gl_da_misaligned_roles = rp.parseDialogActFromString('InformDialogManagement(misaligned-roles)')
gl_da_dialog_invitation = rp.parseDialogActFromString('InformDialogManagement(dialog-invitation)')

gl_da_misaligned_index_pointer = rp.parseDialogActFromString('InformDialogManagement(misaligned-index-pointer)')
gl_da_misaligned_digit_values = rp.parseDialogActFromString('InformDialogManagement(misaligned-digit-values)')


def dealWithMisalignedRoles():
    return gl_da_misaligned_roles

def issueDialogInvitation():
    return gl_da_dialog_invitation

def dealWithMisalignedIndexPointer():
    return gl_da_misaligned_index_pointer

def dealWithMisalignedDigitValues(misaligned_data_value_list):
    print 'dealWithMisalignedDigitValues: ' + str(misaligned_data_value_list)
    return gl_da_misaligned_digit_values
    

        

def testDataAgreement(agent):
    return None
    


#
#
###############################################################################


###############################################################################
#
#Utils
#

#I'm pretty sure there's a shorter way to do this using some pythonic magic like map or something
def extractItemsFromCommaSeparatedListString(str_comma_sep_items):
    str_item_list = []
    #print 'extractItemsFromCommaSeparatedListString(' + str_comma_sep_items + ')'
    
    l1 = str_comma_sep_items.split(',')
    print 'l1: ' + str(l1)
    for item in l1:
        item = item.strip()
        #print ' item: ' + item
        str_item_list.append(item)
    return str_item_list
    



                        

#
#
###############################################################################



###############################################################################
#
#archives
#
