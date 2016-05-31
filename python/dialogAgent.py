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
import thread
import time
import ruleProcessing as rp
from gtts import gTTS

#for playing a wav file
import pyaudio
import wave

#import speech_recognition as sr
#Using a modified version of the speech_recognition library __init__.py file
#to give us the ability to abort out of listening.
import speech_recognition_tpn as sr






#Test just the rules in isolated-rules-test.txt
def loopDialogTest():
    rp.initLFRules('isolated-rules-test.txt')
    loopDialogMain()


gl_agent = None
#gl_turn_history = []   defined below

#This is set by use_debug_mode of loopDialog function
gl_use_wait_timer_p = True

def setUseWaitTimer(val):
    global gl_use_wait_timer_p
    gl_use_wait_timer_p = val


#This is set by use_debug_mode of loopDialog function
gl_use_speech_p = True

def setUseSpeech(val):
    global gl_use_speech_p
    gl_use_speech_p = val



    
#Reset state by creating a new agent and clearing the turn history.
#Test the rules in gl_default_lf_rule_filename.
#Loop one input and print out the set of DialogActs interpreted
def loopDialog(use_debug_mode=False):
    global gl_agent
    global gl_turn_history
    global gl_turn_number
    global gl_time_tick_ms
    global gl_use_wait_timer_p
    global gl_use_speech_p
    if use_debug_mode:
        gl_use_speech_p = False
        gl_use_wait_timer_p = False  
    else:
        gl_use_speech_p = True
        gl_use_wait_timer_p = True

    gl_agent = createBasicAgent()
    gl_turn_history = []  
    gl_turn_number = 0
    gl_pending_question_list = []  
    rp.initLFRulesIfNecessary()
    if gl_use_wait_timer_p:
        createAndStartWaitTimer(gl_time_tick_ms)
    if gl_use_speech_p:
        initializeASR(gl_energy_threshold)
        startNewSpeechRunner()

    #rp.setTell(True)
    openTranscriptFile()

    da_issue_dialog_invitation = issueDialogInvitation()
    da_generated_word_list = rp.generateTextFromDialogAct(da_issue_dialog_invitation)
    print 'da_generated_word_list: ' + str(da_generated_word_list)
    if da_generated_word_list != None:
        str_generated = ' '.join(da_generated_word_list)
        print 'gen: ' + str_generated

        if gl_use_speech_p and len(str_generated) > 0:
            ttsSpeakText(str_generated)
            resetNextTurnBeliefs()

        writeToTranscriptFile('Output: ' + str_generated)
    
    loopDialogMain()


#a list of tuples of Dialog Acts.  Each tuple is of the form,
#  (originator, dialog_act_list)
#Most of the time this will be empty.  The keyboard input, wait timeout,
#and ASR threads all place things on the end.  The loop takes things off the front
gl_dialog_act_queue = []

gl_stop_main_loop = False

def stopMainLoop():
    global gl_stop_main_loop
    print 'stopMainLoop setting gl_stop_main_loop to True'
    gl_stop_main_loop = True


#To deal with the multiple input modalities, this uses a polling strategy.
#The first version had a while loop that blocked on keyboard input.
#Then, wait timeout and ASR ran on separate threads.  But wait timeout has
#to be reset after TTS, and TTS has to shut off ASR so the ASR doesn't respond
#to TTS utterances.  This all got very complicated and the different threads were 
#tripping over themselves.
#
#So the new strategy is that the main loop takes things off an input queue.  The various
#threads are able to add to the queue independently.
#Not sure if thread locks will be necessary.  Probably the queue should be locked
#by anyone modifying it.
def loopDialogMain():
    global gl_dialog_act_queue
    global gl_stop_main_loop
    global gl_agent

    gl_stop_main_loop = False
    startKeyboardInputThread()
    gl_dialog_act_queue = []

    while gl_stop_main_loop == False:
        time.sleep(.01)     #run at 100Hz
        #time.sleep(2.0)     #run at 100Hz
        #print ' in main loop, gl_stop_main_loop: ' + str(gl_stop_main_loop)

        if len(gl_dialog_act_queue) > 0:
            
            da_item = gl_dialog_act_queue[0]
            gl_dialog_act_queue = gl_dialog_act_queue[1:]

            print '\nhandling input from ' + da_item[0]
            da_list = da_item[1]
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

            #printAgentBeliefs(False)
            str_generated = ' '.join(output_word_list)
            print 'gen: ' + str_generated

            if gl_use_speech_p and len(str_generated) > 0:
                ttsSpeakText(str_generated)
                resetNextTurnBeliefs()

            writeToTranscriptFile('Output: ' + str_generated)

            #print '\nInput:'
            sys.stdout.write('Input: ')
            sys.stdout.flush()
        
    stopKeyboardInputThread()
    stopTimer()
    stopSpeechRunner()
    closeTranscriptFile()



def startKeyboardInputThread():
    thread.start_new_thread(keyboardInputThreadFunction, (keyboard_input_callback_function,))

keyboard_input_running_p = False

def stopKeyboardInputThread():
    global keyboard_input_running_p
    print 'stopKeyboardInputThread()'
    keyboard_input_running_p = False

def keyboardInputThreadFunction(keyboard_input_callback_function):
    global keyboard_input_running_p
    keyboard_input_running_p = True

    print 'keyboard input started'
    while keyboard_input_running_p:
        input_string = raw_input('\nKInput: ')
        input_string = rp.removePunctuationAndLowerTextCasing(input_string)

        print 'keyboard sees: ' + input_string
        if input_string == 'quit':
            print 'quit seen, calling stopMainLoop()'
            stopMainLoop()
            keyboard_input_running_p = False

        rule_match_list = rp.applyLFRulesToString(input_string)
        if rule_match_list == False:
            print 'no DialogRule matches found'
        else:
            print 'MATCH: ' + str(rule_match_list);
            da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)
        keyboard_input_callback_function(da_list)

    print 'keyboard input stopped'


def keyboard_input_callback_function(da_list):
    global gl_dialog_act_queue
    gl_dialog_act_queue.append(('Keyboard', da_list))

    






#Treat speech input the same as typed input
def handleSpeechInput(input_string):
    global gl_dialog_act_queue

    writeToTranscriptFile('Input: ' + input_string)
    print 'handleSpeechInput: ' + str(input_string)

    rule_match_list = rp.applyLFRulesToString(input_string)
    if rule_match_list == False:
        print 'no DialogRule matches found'
    else:
        print 'MATCH: ' + str(rule_match_list);
    da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)

    if len(da_list) > 0:
        gl_dialog_act_queue.append(('Speech', da_list))




#self_or_partner is 'self' or 'partner'
#Returns a tuple of the last turn on the part of self or partner:
#  (turn_number, speaker = 'self' or 'partner', DialogAct list, utterance word tuple)
#target_intent_list is a list of target intents that must be present in at least one 
#utterance of the turn in order to return that turn, i.e. one of:
# { InformTopicInfo, InformTopicManagement, RequestTopicInfo,RequestDialogManagement, 
#   CheckTopicInfo, CheckDialogManagement, ConfirmTopicInfo, ConfirmDialogManagement,
#   CorrectionTopicInfo, CorrectionDialogManagemnt}
#Or, target_intent_list can be 'any'
def fetchLastUtteranceFromTurnHistory(self_or_partner, target_intent_list='any'):
    global gl_turn_history
    for item_tup in gl_turn_history:
        if item_tup[1] == self_or_partner:
            if target_intent_list == 'any':
                return item_tup
            for da in item_tup[2]:
                if da.intent in target_intent_list:
                    return item_tup
    return None




#Remember who the next turn belongs to so that the turn beliefs may be reset after
#TTS output has finished speaking.  This essentially resets the wait timer for when 
#self decides that their turn belief exceeds threshold because they thought it was
#partner's turn but partner hasn't taken it.
gl_next_turn_holder = 'either'

def resetNextTurnBeliefs():
    global gl_agent
    gl_agent.setTurn(gl_next_turn_holder)






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
        self.self_dialog_model = None
        self.partner_dialog_model = None
        self.setRole('banter')                 #initialize with 'banter' role


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

    #turn_value can be 'self', 'either', 'partner'
    def setTurn(self, turn_value):
        global gl_next_turn_holder
        gl_next_turn_holder = turn_value
        self.self_dialog_model.turn.setAllConfidenceInOne(turn_value)
        self.partner_dialog_model.turn.setAllConfidenceInOne(turn_value)



    def adjustTurnTowardSelf(self, delta):
        self.self_dialog_model.adjustTurnTowardSelf(delta)
        self.partner_dialog_model.adjustTurnTowardSelf(delta)   #toward absolute self, not toward partner to agent.self

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
        self.turn = None                         #An OrderedMultinomialBelief: ['self', 'either', 'partner'] 
                                                 # turn value is absolute not relative to the dialog model. 
                                                 # So turn = 'self' always means the turn belongs to the agent.self speaker,
                                                 # regardless of whether the dialog model is self_dialog_model or partner_dialog_model.
        self.protocol_chunck_size = None         #An OrderedMultinomialBelief: [1, 2, 3, 10]
        self.protocol_handshaking = None         #An OrderedMultinomialBelief: [1, 2, 3, 4, 5]  1 = never, 5 = every turn


    #who is one of 'self', 'either', 'partner'
    def getTurnConfidence(self, who):
        return self.turn.getValueConfidence(who)

    def adjustTurnTowardSelf(self, delta):
        self_conf = self.turn.getValueConfidence('self')
        new_self_conf = max(0.0, min(1.0, self_conf + delta))
        self.turn.setValueConfidenceNormalizeOthers('self', new_self_conf)


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
    dm.data_index_pointer = OrderedMultinomialBelief(gl_10_digit_index_list)
    dm.data_index_pointer.setAllConfidenceInOne(0)                      #initialize starting at the first digit
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = OrderedMultinomialBelief(gl_turn_mnb)
    dm.turn.setAllConfidenceInOne('either')                             #will get overridden
    dm.protocol_chunk_size = OrderedMultinomialBelief(gl_chunk_size_mnb)
    dm.protocol_chunk_size.setAllConfidenceInTwo(3, 4)                  #initialize with chunk size 3/4 
    dm.protocol_handshaking = OrderedMultinomialBelief(gl_handshake_level_mnb)
    dm.protocol_handshaking.setAllConfidenceInOne(3)                    #initialize with moderate handshaking
    return dm


def initBanterDialogModel(self_or_partner):
    global gl_default_phone_number
    dm = DialogModel()
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    dm.data_index_pointer = OrderedMultinomialBelief(gl_10_digit_index_list)
    dm.data_index_pointer.setEquallyDistributed()                       #no index pointer
    dm.readiness = BooleanBelief()
    dm.readiness.setBeliefInTrue(0)                                     #initialize not being ready
    dm.turn = OrderedMultinomialBelief(gl_turn_mnb)
    dm.turn.setAllConfidenceInOne('either')
    dm.protocol_chunk_size = OrderedMultinomialBelief(gl_chunk_size_mnb)
    dm.protocol_chunk_size.setAllConfidenceInTwo(3, 4)                 #initialize with chunk size 3/4 
    dm.protocol_handshaking = OrderedMultinomialBelief(gl_handshake_level_mnb)
    dm.protocol_handshaking.setAllConfidenceInOne(3)                   #initialize with moderate handshaking
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
                             'exchange':[3,5],\
                             'line-number':[6,9]}


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
    def setNthPhoneNumberDigit(self, nth, digit_value, prob=1.0):
        self.data_beliefs[nth].setValueProb(digit_value, prob)
        #self.data_beliefs[nth].setValueDefinite(digit_value)

    def resetUnknownDigitValues(self):
        for digit_i in range(0, 10):
            self.data_beliefs[digit_i].setValueUnknown()

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
        pstr = '( ' + self.data_beliefs[0].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[1].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[2].getPrintStringAbbrev() + ' ) ' +\
                      self.data_beliefs[3].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[4].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[5].getPrintStringAbbrev() + ' - ' +\
                      self.data_beliefs[6].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[7].getPrintStringAbbrev() + ' ' +\
                      self.data_beliefs[8].getPrintStringAbbrev() + ' ' +\
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

    #sets the primary value val1_value to digit_value with belief=prob, the remaining belief goes to val_unknown
    def setValueProb(self, digit_value, prob):
        self.val1_value = digit_value
        self.val1_confidence = prob
        self.val2_value = '-'
        self.val2_confidence = 0.0
        self.val_unknown_confidence = 1.0-prob

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
    def __init__(self, value_list):
        #sets up:
        #self.value_list
        #self.confidence_list
        #self.value_name_index_map
        if len(value_list) == 0:
            value_list = [None]
        self.resetValueList(value_list)

    def resetValueList(self, value_list):
        self.value_list = value_list[:]
        conf = 1.0 / len(value_list)
        self.confidence_list = len(value_list) * [ 1.0/len(value_list) ]
        self.value_name_index_map = {}
        for i in range(0, len(value_list)):
            self.value_name_index_map[value_list[i]] = i

    def setEquallyDistributed(self):
        conf = 1.0 / len(self.value_list)
        self.confidence_list = len(self.value_list) * [ 1.0/len(self.value_list) ]

    def setAllConfidenceInOne(self, all_confidence_value):
        self.confidence_list = len(self.value_list) * [ 0.0 ]
        index = self.value_name_index_map.get(all_confidence_value)
        if index == None:
            print 'setAllConfidenceInOne could not find index for all_confidence_value: ' + str(all_confidence_value)
            return
        self.confidence_list[index] = 1.0

    def setAllConfidenceInTwo(self, half_confidence_value_1, half_confidence_value_2):
        self.confidence_list = len(self.value_list) * [ 0.0 ]
        index1 = self.value_name_index_map.get(half_confidence_value_1)
        index2 = self.value_name_index_map.get(half_confidence_value_2)
        if index1 == None:
            print 'setAllConfidenceInTwo could not find index for all_confidence_value: ' + str(half_confidence_value_1)
            return
        if index2 == None:
            print 'setAllConfidenceInTwo could not find index for all_confidence_value: ' + str(half_confidence_value_2)
            return
        self.confidence_list[index1] = .5
        self.confidence_list[index2] = .5


    #returns -1 if the dominant value is out of range
    # (maybe None would be better?)
    def getDominantValue(self):
        max_confidence = 0.0
        max_value = -1
        for i in range(0, len(self.value_list)):
            confidence = self.confidence_list[i]
            if confidence > max_confidence:
                max_confidence = confidence
                max_value = self.value_list[i]
        return max_value

    #returns a tuple of tuples ((max_value, max_conf), (second_max_value, second_max_conf))
    def getTwoMostDominantValues(self):
        max_conf = 0.0
        max_value = -1
        second_max_conf = 0.0
        second_max_value = 0.0
        for i in range(0, len(self.value_list)):
            value = self.value_list[i]
            confidence = self.confidence_list[i]
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

    def getValueConfidence(self, item_value_name):
        index = self.value_name_index_map.get(item_value_name)
        if index == None:
            print 'getValueConfidence could not find index for item_value_name: ' + str(item_value_name)
            return None
        return self.confidence_list[index]


    #sets the confidence in item_name to new_item_confidence
    #then adjusts the confidence in all other values to normalize to 1
    def setValueConfidenceNormalizeOthers(self, item_name, new_item_confidence):
        if new_item_confidence < 0 or new_item_confidence > 1:
            print 'setValueConfidenceNormalizeOthers got new_item_confidence ' + str(new_item_confidence) + ' out of bounds for item_name: ' + str(item_name)
            new_item_confidence = min(1, max(0, new_item_confidence))

        item_index = self.value_name_index_map.get(item_name)
        if item_index == None:
            print 'setValueConfidenceNormalizeOthers could not find index for item_value_name: ' + str(item_value_name)
            return
        previous_conf = self.confidence_list[item_index]
        delta = new_item_confidence - previous_conf
        other_delta = -delta / (len(self.value_list) - 1)
        self.confidence_list[item_index] = new_item_confidence
        iter = 0
        while abs(other_delta) > .001:
            non_item_conf_sum = 0
            for i in range(0, len(self.value_list)):
                if i == item_index:
                    continue
                self.confidence_list[i] = max(0, min(1, self.confidence_list[i] + other_delta))
                non_item_conf_sum += self.confidence_list[i]
            #believe it or not I guessed right and got the signs correct on my first try
            other_delta = ((1 - self.confidence_list[item_index]) - non_item_conf_sum) / (len(self.value_list) - 1)
            #print str(iter) + ' conf_list: ' + str(self.confidence_list)
            #print ' non_item_conf_sum: ' + str(non_item_conf_sum) + ' other_delta: ' + str(other_delta)
            iter += 1
        

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        conf_threshold_to_print = .1     #only print confidences > threshold .1
        temp_list = []
        for i in range(0, len(self.value_list)):
            temp_list.append((self.value_list[i], self.confidence_list[i]))
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



def printAgentBeliefs(abbrev_p = True):
    global gl_agent
    if gl_agent.self_dialog_model == None:
        return
    print 'self: iptr     ' + str(gl_agent.self_dialog_model.data_index_pointer.getDominantValue())
    if abbrev_p:
        print gl_agent.self_dialog_model.data_model.getPrintStringAbbrev()
    else:
        print gl_agent.self_dialog_model.data_model.getPrintString()
    print 'partner: iptr: ' + str(gl_agent.partner_dialog_model.data_index_pointer.getDominantValue())
    if abbrev_p:
        print gl_agent.partner_dialog_model.data_model.getPrintStringAbbrev()
    else:
        print gl_agent.partner_dialog_model.data_model.getPrintString()



#
#
###############################################################################

###############################################################################
#
#
#


gl_turn_number = 0

#each turn is a tuple: (turn_number, speaker = 'self' or 'partner', DialogAct list, utterance_word_tuple)
#DialogAct list is a list of DialogAct instances, not their string versions
#for now we may not be including the utterance word tuple because that has to be gotten from the ruleProcessing side
#Each new turn is prepended to the front of the list so the most recent turn is [0]
gl_turn_history = []


#A list tuples for Request, Check, or possibly other DialogActs, that represent questions that are still pending.
#(turn_number, speaker = 'self' or 'partner', DialogAct, utterance_word_tuple)
#These are ordered by turn, most recent first.
#Unlike gl_turn_history, there is only one DialogAct per tuple, so if a turn includes multiple
#questions, these will be stacked up.
#borrowed straight from Otto
gl_pending_question_list = []  


#A list of DialogActs that represent the most recently immediate topical data objects.
#For example, the most recently discussed digit sequence.
gl_most_recent_data_topic_da_list = []



def generateResponseToInputDialog(user_da_list):
    global gl_turn_history
    global gl_turn_number
    global gl_most_recent_data_topic_da_list

    if len(user_da_list) == 0:
        print 'what? user_da_list length is 0'
        return user_da_list

    gl_turn_history.insert(0, (gl_turn_number, 'partner', user_da_list))
    gl_turn_number += 1
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
    elif user_da_list[0].intent == 'RequestAction':
        da_response = handleRequestAction(user_da_list)

    
    if da_response != None:
        gl_turn_history.insert(0, (gl_turn_number, 'self', da_response))
        gl_turn_number += 1
    else:
        print '!Did not generate a response to user input DialogActs:'
        for user_da in user_da_list:
            user_da.printSelf()
        da_response = []

    #Determine if this response merits becoming the most recent data topic of discussion
    response_to_become_most_recent_data_topic_p = False
    for da in da_response:
        if da.getPrintString().find('ItemValue') >= 0:
            response_to_become_most_recent_data_topic_p = True
            break
    if response_to_become_most_recent_data_topic_p == True:
        gl_most_recent_data_topic_da_list = da_response[:]

    print ' Updating gl_most_recent_data_topic_da_list:'
    for da in gl_most_recent_data_topic_da_list:
        print da.getPrintString()
    print ' ..'
        
    gl_agent.setTurn('partner')
    return da_response



gl_da_inform_dm_greeting = rp.parseDialogActFromString('InformDialogManagement(greeting)')
gl_str_da_inform_dm_greeting = 'InformDialogManagement(greeting)'

gl_da_check_readiness = rp.parseDialogActFromString('CheckDialogManagement(other-readiness)')
gl_str_da_check_readiness = 'CheckDialogManagement(other-readiness)'

gl_da_what_is_your_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(agent-name))')
gl_str_da_my_name_is = 'InformTopicInfo(self-name, Name($1))'

gl_da_what_is_my_name = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(user-name))')
gl_str_da_your_name_is = 'InformTopicInfo(partner-name, Name($1))'

gl_da_tell_me_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic(telephone-number))')
gl_da_tell_you_phone_number = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), InfoTopic(telephone-number))')

gl_da_tell_me_topic_info = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-me), InfoTopic($1))')
gl_da_tell_you_topic_info = rp.parseDialogActFromString('RequestTopicInfo(SendReceive(tell-you), InfoTopic($1))')

gl_da_request_topic_info = rp.parseDialogActFromString('RequestTopicInfo(ItemType($1))')
gl_str_da_request_topic_info = 'RequestTopicInfo(ItemType($1))'


#This is the initial parts of a DialogAct,
#RequestTopicInfo(request-confirmation, ItemValue(Digit($1))) or 
#RequestTopicInfo(request-confirmation, ItemValue(DigitSequence($1, $2, ...)))
#Instead of listing out all of the argugment variations, we simply detect the initial part
#and parse out the arguments in the functions that handle this.
#The same applies for InformTopicInfo with one or more data item values.
#The following underscore _ indicates an incomplete LogicalForm.
gl_str_da_request_confirmation_ = 'RequestTopicInfo(request-confirmation'

#Similar to above for 
#RequestDialogManagement(clarification-utterance-past, ItemValue(Digit($1))) 
#RequestDialogManagement(clarification-utterance-past, ItemValue(DigitSequence($1, $2, ...)))
gl_str_da_request_dm_clarification_utterance_ = 'RequestDialogManagement(clarification-utterance'





gl_da_say_item_type = rp.parseDialogActFromString('InformTopicInfo(SayItemType($1))')
gl_str_da_say_item_type = 'InformTopicInfo(SayItemType($1))'


gl_da_affirmation_okay = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-okay)')
gl_str_da_affirmation_okay = 'ConfirmDialogManagement(affirmation-okay)'

gl_da_affirmation_yes = rp.parseDialogActFromString('ConfirmDialogManagement(affirmation-yes)')
gl_str_da_affirmation_yes = 'ConfirmDialogManagement(affirmation-yes)'


gl_da_affirmation = rp.parseDialogActFromString('ConfirmDialogManagement($1)')

gl_da_correction_dm_negation = rp.parseDialogActFromString('CorrectionDialogManagement(negation)')
gl_str_da_correction_dm_negation = 'CorrectionDialogManagement(negation)'


#e.g. 'that is the [area code]'
gl_da_correction_dm_item_type_present = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction-present, ItemType($1))')
gl_str_da_correction_dm_item_type_present = 'CorrectionTopicInfo(partner-correction-present, ItemType($1))'

#e.g.. 'that was the [area code]'
gl_da_correction_dm_item_type_past = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction-past, ItemType($1))')
gl_str_da_correction_dm_item_type_past = 'CorrectionTopicInfo(partner-correction-past, ItemType($1))'


#e.g. 'is the area code'
gl_da_inform_item_type = rp.parseDialogActFromString('InformTopicInfo(info-type-present, ItemType($1))')
gl_str_da_inform_item_type = 'InformTopicInfo(info-type-present, ItemType($1))'



#g.e. 'six is the the digit
gl_da_correction_dm_item_value_digit_item_type_present = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction-present, InfoTopic(ItemValue(Digit($1))), ItemType($2))')
gl_str_da_correction_dm_item_value_digit_item_type_present = 'CorrectionTopicInfo(partner-correction-present, InfoTopic(ItemValue(Digit($1))), ItemType($2))'

#g.e. 'six five zero is the the area code
#Not doing it this way because it requires spelling out each DigitSequence arugment.
#Instead, we'll generate this form of output by stringing together indivdual InformTopicInfo(Digit dialog acts for each digit
#gl_da_correction_dm_item_value_digit_sequence_item_type_present = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction-present, #InfoTopic(ItemValue(DigitSequence($1))), ItemType($2))')
#gl_str_da_correction_dm_item_value_digit_sequence_item_type_present = 'CorrectionTopicInfo(partner-correction-present, InfoTopic(ItemValue(DigitSequence($1))), ItemType($2))'


gl_da_self_ready = rp.parseDialogActFromString('InformDialogManagement(self-readiness)')
gl_da_self_not_ready = rp.parseDialogActFromString('InformDialogManagement(self-not-readiness)')
gl_da_all_done = rp.parseDialogActFromString('InformTopicInfo(all-done)')

gl_da_what = rp.parseDialogActFromString('RequestDialogManagement(what)')
gl_str_da_what = 'RequestDialogManagement(what)'


gl_da_misalignment_self_hearing_or_understanding = rp.parseDialogActFromString('RequestDialogManagement(misalignment-self-hearing-or-understanding)')
gl_str_da_misalignment_self_hearing_or_understanding = 'RequestDialogManagement(misalignment-self-hearing-or-understanding)'

gl_da_misalignment_self_hearing_or_understanding_pronoun_ref = rp.parseDialogActFromString('RequestDialogManagement(misalignment-self-hearing-or-understanding, pronoun-ref)')
gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref = 'RequestDialogManagement(misalignment-self-hearing-or-understanding, pronoun-ref)'

gl_da_misalignment_self_hearing_or_understanding_item_type = rp.parseDialogActFromString('RequestDialogManagement(misalignment-self-hearing-or-understanding, ItemType($1))')
gl_str_da_misalignment_self_hearing_or_understanding_item_type = 'RequestDialogManagement(misalignment-self-hearing-or-understanding, ItemType($1))'

gl_da_misalignment_request_repeat = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat)')
gl_str_da_misalignment_request_repeat = 'RequestDialogManagement(misalignment-request-repeat)'



gl_da_misalignment_request_repeat_pronoun_ref = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat, pronoun-ref)')
gl_str_da_misalignment_request_repeat_pronoun_ref = 'RequestDialogManagement(misalignment-request-repeat, pronoun-ref)'

gl_da_misalignment_request_repeat_item_type = rp.parseDialogActFromString('RequestDialogManagement(misalignment-request-repeat, ItemType($1))')
gl_str_da_misalignment_request_repeat_item_type = 'RequestDialogManagement(misalignment-request-repeat, ItemType($1))'

gl_da_inform_dm_repeat_intention = rp.parseDialogActFromString('InformDialogManagement(repeat-intention)')
gl_str_da_inform_dm_repeat_intention = 'InformDialogManagement(repeat-intention)'

gl_da_misalignment_start_again = rp.parseDialogActFromString('RequestDialogManagement(misalignment-start-again)')
gl_str_da_misalignment_start_again = 'RequestDialogManagement(misalignment-start-again)'




gl_da_correction_topic_info = rp.parseDialogActFromString('CorrectionTopicInfo(partner-correction)')
gl_str_da_correction_topic_info = 'CorrectionTopicInfo(partner-correction)'


gl_da_correction_topic_info_negation_polite = rp.parseDialogActFromString('CorrectionTopicInfo(negation-polite)')
gl_str_da_correction_topic_info_negation_polite = 'CorrectionTopicInfo(negation-polite)'

gl_da_correction_topic_info_negation_polite_partner_correction = rp.parseDialogActFromString('CorrectionTopicInfo(negation-polite-partner-correction)')
gl_str_da_correction_topic_info_negation_polite_partner_correction = 'CorrectionTopicInfo(negation-polite-partner-correction)'



gl_da_clarification_utterance_past = rp.parseDialogActFromString('RequestDialogManagement(clarification-utterance-past, ItemType($1))')
gl_str_da_clarification_utterance_past = 'RequestDialogManagement(clarification-utterance-past, ItemType($1))'

gl_da_clarification_utterance_present = rp.parseDialogActFromString('RequestDialogManagement(clarification-utterance-present, ItemType($1))')
gl_str_da_clarification_utterance_present = 'RequestDialogManagement(clarification-utterance-present, ItemType($1))'


gl_digit_list = ['zero', 'oh', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']


gl_da_request_action_echo = rp.parseDialogActFromString('RequestAction(speak)')
gl_str_da_request_action_echo = 'RequestAction(speak)'


gl_da_misaligned_roles = rp.parseDialogActFromString('InformDialogManagement(misaligned-roles)')
gl_da_dialog_invitation = rp.parseDialogActFromString('InformDialogManagement(dialog-invitation)')

gl_da_misaligned_index_pointer = rp.parseDialogActFromString('InformDialogManagement(misaligned-index-pointer)')
gl_da_misaligned_digit_values = rp.parseDialogActFromString('InformDialogManagement(misaligned-digit-values)')


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
#    In this case, try to align the partner's stated check digits with the self data model
#    in order to infer what digits the partner is checking, some of which they might have
#    checked before.  If alignment is successful and unambiguous, then it allows us to advance
#    the partner index pointer, and set self data index pointer accordingly.
#  - partner check-confirming digit values mixed with an indication of misunderstanding, e.g. what?
#    In this case, place the partner data_index_pointer at the first what?, but send
#    context digits mirroring the sender's
#
#These are InformTopicInfo because we are not currently able to parse input as multiple
#candidate DialogActs with different intents.
def handleInformTopicInfo_SendRole(da_list):
    global gl_agent

    print 'handleInformTopicInfo '
    #printAgentBeliefs()

    (partner_expresses_confusion_p, match_count, check_match_segment_name,\
         partner_digit_word_sequence) = comparePartnerReportedDataAgainstSelfData(da_list)

    self_data_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()

    #This is an easy out, to be made more sophisticated later
    if partner_expresses_confusion_p:
        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret = [gl_da_inform_dm_repeat_intention]
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret
    
    #Only if check-confirm match was validated against self's belief model, update self's model
    #for what partner believes about the data.
    if match_count > 0:       

        possiblyAdjustChunkSize(len(partner_digit_word_sequence))
        #1.0 is full confidence that the partner's data belief is as self heard it
        partner_dm = gl_agent.partner_dialog_model
        newly_matched_digits = []
        for digit_i in range(self_data_index_pointer, self_data_index_pointer + match_count):
            digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
            data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            correct_digit_value = data_value_tuple[0]
            partner_dm.data_model.setNthPhoneNumberDigit(digit_i, correct_digit_value, 1.0)
            partner_index_pointer_value = partner_dm.data_index_pointer.getDominantValue()
            partner_dm.data_index_pointer.setAllConfidenceInOne(digit_i+1)

        #printAgentBeliefs()
        middle_or_at_end = advanceSelfIndexPointer(gl_agent, match_count)  
        print 'after advanceSelfIndexPointer...'
        #printAgentBeliefs()
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()
        #print 'self_belief_partner_is wrong...' + str(self_belief_partner_is_wrong_digit_indices) + ' self_belief unknown... ' +\
        #    str(self_belief_partner_registers_unknown_digit_indices)

        if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
                len(self_belief_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return [gl_da_all_done];

        else:
            return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()

    ret = [gl_da_inform_dm_repeat_intention]
    ret.extend(prepareNextDataChunk(gl_agent))
    return ret


#This was lifted from handleInformTopicData_Send in order to use it also
#in RequestTopicInfo(request-confirmation)
#The partner is providing a list of DialogActs that include information about digit data.
#(The DialogActs are strung together from a single utterance.)
#The DialogActs might also include indicators of confusion, such as what?
#These DialogActs need to be compared with correct digit data, partly though alignment search.
#This returns a tuple: 
# (partner_expresses_confusion_p, match_count, check_match_segment_name, partner_digit_word_sequence)
#
def comparePartnerReportedDataAgainstSelfData(da_list):
    print 'comparePartnerReportedDataAgainstSelfData(da_list)'
    for da in da_list:
        print da.getPrintString()

    partner_digit_word_sequence = []
    partner_expresses_confusion_p = False

    #could be an interspersing of ItemValue(Digit( and ItemValue(DigitSequence
    for da in da_list:
        str_da = da.getPrintString()
        print str_da
        d_index = str_da.find('ItemValue(Digit(')
        ds_index = str_da.find('ItemValue(DigitSequence(')
        if d_index >= 0:
            start_index = d_index + len('ItemValue(Digit(')
            rp_index = str_da.find(')', start_index)
            partner_check_digit_value = str_da[start_index:rp_index]
            partner_digit_word_sequence.append(partner_check_digit_value)

        elif ds_index >= 0:
            start_index = ds_index + len('ItemValue(DigitSequence(')
            rp_index = str_da.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(str_da[start_index:rp_index])
            partner_digit_word_sequence.extend(digit_value_list)

        #Commenting this out because it inserts '?' for things like "was that six five zero" 
        ##This applies to an isolated 'what?' or other non-digit which we intend to have substituted for a digit value so
        ##is indicative of confusion
        ##But the danger is that 'what' said with other words will be interpreted as confusion when it is not,
        ##and the system speaks 'I'll repeat that' when they really shouldn't.
        #elif str_da not in gl_digit_list and str_da.find('ConfirmDialogManagement') < 0:
        #    #partner indicates confusion so we surmise they have not advanced their index pointer with this data chunk.
        #    #So reset the tentative_partner_index_pointer.
        #    partner_expresses_confusion_p = True
        #    #Add ? partner utterance explicitly into the list of digits we heard them say, in order to
        #    #pinpoint the index pointer for their indicated check-confusion
        #    partner_digit_word_sequence.append('?')

    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
    last_self_utterance_da_list = last_self_utterance_tup[2]
    last_sent_digit_value_list = collectDataValuesFromDialogActs(last_self_utterance_da_list)
    self_data_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()

    print 'last_sent_digit_value_list: ' + str(last_sent_digit_value_list) + ' partner_digit_word_sequence: ' + str(partner_digit_word_sequence)

    #Here try to align partner's check digit sequence with what self has just provided as a partial digit sequence,
    #or else with the context of previously provided values, or even with correct data that has not been provided
    #in this conversation (i.e. if partner knows the phone number already)
    
    #This returns match_count = 0 if the partner_digit_word_sequence contains any errors or an 
    #alignment match to self's data model cannot be found.
    check_match_tup = registerCheckDataWithLastSaidDataAndDataModel(partner_digit_word_sequence, last_sent_digit_value_list, self_data_index_pointer)

    match_count = check_match_tup[0]
    print 'match_count: ' + str(match_count)

    return (partner_expresses_confusion_p, match_count, check_match_tup[1], partner_digit_word_sequence)




        


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
        return handleInformDialogManagement_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleInformDialogManagement_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        da0 = da_list[0]
        str_da0 = da0.getPrintString()
        print 'str_da0: ' + str_da0
        if str_da0 == gl_str_da_inform_dm_greeting:
            return [gl_da_inform_dm_greeting, gl_da_dialog_invitation]
    



def handleInformDialogManagement_SendRole(da_list):
    print 'handleInformDialogManagement_SendRole not written yet'
    return None


def handleInformDialogManagement_ReceiveRole(da_list):
    print 'handleInformDialogManagement_ReceiveRole not written yet'
    return None


def handleInformDialogManagement_BanterRole(da_list):
    print 'handleInformDialogManagement_BanterRole not written yet'
    return None




#should have something here about partner indicating readiness




####
#
#Request
#
#Request information about topic or dialog management,
#or request adjustment in dialog management protocol.
#Assumption that the speaker's belief confidence is low.
#

def handleRequestTopicInfo(da_list):
    global gl_most_recent_data_topic_da_list

    #Determine if the utterance from partner merits becoming the most recent data topic of discussion
    response_to_become_most_recent_data_topic_p = False
    for da in da_list:
        if da.getPrintString().find('ItemValue') >= 0:
            response_to_become_most_recent_data_topic_p = True
            break
    if response_to_become_most_recent_data_topic_p == True:
        gl_most_recent_data_topic_da_list = da_list[:]

    if gl_agent.send_receive_role == 'send':
        return handleRequestTopicInfo_SendRole(da_list)
    elif gl_agent.send_receive_role == 'receive':
        return handleRequestTopicInfo_ReceiveRole(da_list)
    elif gl_agent.send_receive_role == 'banter':
        return handleRequestTopicInfo_BanterRole(da_list)



#RequestTopicInfo
#Request information about topic
#
def handleRequestTopicInfo_SendRole(da_list):
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
                #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
                chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_chunk_name)
                for i in range(chunk_indices[0], chunk_indices[1] + 1):
                    data_index_pointer = gl_10_digit_index_list[i]
                    gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
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

    #handle "User: was that seven two six"
    #very similar to how we handle InformTopicInfo of one or more data items
    str_da_rti = da_request_topic_info.getPrintString()
    if str_da_rti.find(gl_str_da_request_confirmation_) == 0:
        return handleRequestTopicInfo_RequestConfirmation(da_list)

    print 'handleRequestTopicInfo has no handler for request ' + da_request_topic_info.getPrintString()
    return da_list;




#handle info receiver:  "was that seven two six?"
#borrows from handleInformTopicInfo_SendRole which covers for handleCheckTopicInfo_SendRole
#The main difference here is that the reply assumes the speaker requesting confirmation has
#low confidence in the information, so this gives the Topic Info Receiver a chance to 
#confirm or ask further questions. So, this increases confidence that the TIR has the
#correct data, but does not move on to the next segment.
def handleRequestTopicInfo_RequestConfirmation(da_list):
    global gl_agent
    global gl_most_recent_data_topic_da_list

    print 'handleRequestTopicInfo_RequestConfirmation '
    #printAgentBeliefs()

    (partner_expresses_confusion_p, match_count, check_match_segment_name,\
         partner_digit_word_sequence) = comparePartnerReportedDataAgainstSelfData(da_list)

    self_data_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()
    print 'after compare... self_data_index_pointer: ' + str(self_data_index_pointer)

    #This is an easy out, to be made more sophisticated later
    if partner_expresses_confusion_p:
        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret = [gl_da_inform_dm_repeat_intention]
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret
    
    #Only if check-confirm match was validated against self's belief model, update self's model
    #for what partner believes about the data.
    if match_count > 0:       

        possiblyAdjustChunkSize(len(partner_digit_word_sequence))
        #1.0 is full confidence that the partner's data belief is as self heard it
        partner_dm = gl_agent.partner_dialog_model
        newly_matched_digits = []
        for digit_i in range(self_data_index_pointer, self_data_index_pointer + match_count):
            digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
            data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            correct_digit_value = data_value_tuple[0]
            partner_dm.data_model.setNthPhoneNumberDigit(digit_i, correct_digit_value, 1.0)

            #since this was a request about data but has not been confirmed, don't advance partnre index pointer
            #because partner has not confirmed that they have accepted this data
            #partner_dm.data_index_pointer.setAllConfidenceInOne(digit_i+1)

        #printAgentBeliefs()
        #since this was a request about data but has not been confirmed, don't advance self index pointer
        #middle_or_at_end = advanceSelfIndexPointer(gl_agent, match_count)  
        #print 'after advanceSelfIndexPointer...'
        print 'not advancing self index pointer which is:' + str(gl_agent.self_dialog_model.data_index_pointer.getDominantValue())
        #printAgentBeliefs()
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

        #since this was a request, don't move on with the next chunk, just issue confirmation
        #and a reiteration of what data was confirmed
        ret = [gl_da_affirmation_yes]
        #substitute InformTopicInfo for RequestTopicInfo of the gl_most_recent_data_topic_list
        data_value_list = collectDataValuesFromDialogActs(gl_most_recent_data_topic_da_list)
        print 'data_value_list: ' + str(data_value_list)
            
        if len(data_value_list) >= 1:
            inform_digits_da = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
            ret.append(inform_digits_da)
            #ret.extend(gl_most_recent_data_topic_da_list)
            return ret

    #since we haven't advanced the self data index pointer, then actually we are re-sending the 
    #previous chunk. 
    #Issue polite correction to the request: "sorry no it's"
    ret = [ gl_da_correction_topic_info_negation_polite_partner_correction ]
    ret.extend(prepareNextDataChunk(gl_agent))
    return ret





def handleRequestTopicInfo_ReceiveRole(da_list):
    print 'handleRequestTopicInfo_ReceiveRole not written yet'
    return None


def handleRequestTopicInfo_BanterRole(da_list):
    print 'handleRequestTopicInfo_BanterRole da_list: '
    for da in da_list:
        da.printSelf()

    da_request_topic_info = da_list[0]

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
                #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
                chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_chunk_name)
                for i in range(chunk_indices[0], chunk_indices[1] + 1):
                    data_index_pointer = gl_10_digit_index_list[i]
                    gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
                return handleSendSegmentChunkNameAndData(segment_chunk_name)

    #handle 'User: take this phone number'
    mapping = rp.recursivelyMapDialogRule(gl_da_tell_you_phone_number, da_request_topic_info)
    if mapping != None:
        gl_agent.setRole('receive')
        return [gl_da_affirmation_okay, gl_da_self_ready]

    #handle "User: was that seven two six"
    #very similar to how we handle InformTopicInfo of one or more data items
    str_da_rti = da_request_topic_info.getPrintString()
    if str_da_rti.find(gl_str_da_request_confirmation_) == 0:
        return handleRequestTopicInfo_RequestConfirmation(da_list)

    print 'handleRequestTopicInfo has no handler for request ' + da_request_topic_info.getPrintString()
    return None









#RequestDialogManagement
#Request information about dialog management, or request adjustment in dialog management protocol.
#
def handleRequestDialogManagement(da_list):
    global gl_agent
    global gl_most_recent_data_topic_da_list
    da_request_dm = da_list[0] 
    str_da_request_dm = da_request_dm.getPrintString()

    #Determine if the utterance from partner merits becoming the most recent data topic of discussion
    response_to_become_most_recent_data_topic_p = False
    for da in da_list:
        if da.getPrintString().find('ItemValue') >= 0:
            response_to_become_most_recent_data_topic_p = True
            break
    if response_to_become_most_recent_data_topic_p == True:
        gl_most_recent_data_topic_da_list = da_list[:]

    print 'handleRequestDialogManagement()'
    for da in da_list:
        da.printSelf()

    #handle "i didn't get that"
    #print 'str_da_request_dm: ' + str_da_request_dm
    #print 'gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref: ' + gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref
    #handle restart 'let's start again'
    if str_da_request_dm == gl_str_da_misalignment_start_again:
        if gl_agent.send_receive_role == 'send':
            initializeStatesToSendPhoneNumberData(gl_agent)
            str_da_say_the_telephone_number_is = gl_str_da_say_item_type.replace('$1', 'area-code')
            da_say_the_telephone_number_is = rp.parseDialogActFromString(str_da_say_the_telephone_number_is)
            da_ret = [ gl_da_affirmation_okay, da_say_the_telephone_number_is]
            da_first_chunk = prepareNextDataChunk(gl_agent)
            da_ret.extend(da_first_chunk)
            return da_ret

    #handle what was it again?   pronoun_ref, repeat the last utterance containing topic info
    if str_da_request_dm == gl_str_da_misalignment_request_repeat_pronoun_ref:
        #print ' fetch InformTopicInfo'
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        if last_self_utterance_tup != None:
            return last_self_utterance_tup[2]

    #handle   I did not get that
    if str_da_request_dm == gl_str_da_misalignment_self_hearing_or_understanding_pronoun_ref: 
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
        if last_self_utterance_tup != None:
            return last_self_utterance_tup[2]

    #handle "repeat that"   no pronoun ref so repeat the last utterance
    if str_da_request_dm == gl_str_da_misalignment_request_repeat:
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        if last_self_utterance_tup != None:
            #print 'last_self_utterance_tup: ' + str(last_self_utterance_tup)
            return last_self_utterance_tup[2]

    #handle what?      not a pronoun ref so just repeat the last utterance
    if str_da_request_dm == gl_str_da_what:
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        if last_self_utterance_tup != None:
            return last_self_utterance_tup[2]

    #handle what did you say?  no pronoun ref, so just repeat the last utterance
    if str_da_request_dm == gl_str_da_misalignment_self_hearing_or_understanding:
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        if last_self_utterance_tup != None:
            return last_self_utterance_tup[2]

    #handle "User: did you say seven two six"
    #very similar to how we handle InformTopicInfo of one or more data items
    if str_da_request_dm.find(gl_str_da_request_dm_clarification_utterance_) == 0:
        #Even though this is a slightly different utterance, 'did you say $1' instead of 
        #'was that $1', we can handle it in the same way as a request for confirmation of data.
        return handleRequestTopicInfo_RequestConfirmation(da_list)


    #print 'str_da_request_dm: ' + str_da_request_dm
    #print 'gl_da_misalignment_self_hearing_or_understanding_item_type: ' + gl_da_misalignment_self_hearing_or_understanding_item_type.getPrintString()
    #handle "I did not understand the area code, etc"
    mapping_ma = rp.recursivelyMapDialogRule(gl_da_misalignment_self_hearing_or_understanding_item_type, da_request_dm)
    #handle "repeat the area code, etc'
    mapping_rr = rp.recursivelyMapDialogRule(gl_da_misalignment_request_repeat_item_type, da_request_dm)

    mapping = None
    if mapping_ma != None:
        mapping = mapping_ma
    if mapping_rr != None:
        mapping = mapping_rr
    if mapping != None:
        misunderstood_item_type = mapping.get('1')
        if misunderstood_item_type in gl_agent.self_dialog_model.data_model.data_indices.keys():
            #If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
            chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_chunk_name)
            for i in range(chunk_indices[0], chunk_indices[1] + 1):
                data_index_pointer = gl_10_digit_index_list[i]
                gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)
            return handleSendSegmentChunkNameAndData(misunderstood_item_type)

    #handle "was that the area code?"
    mapping_cpa = rp.recursivelyMapDialogRule(gl_da_clarification_utterance_past, da_request_dm)
    print 'mapping_cpa: ' + str(mapping_cpa)
    #handle "is that the area code?"
    mapping_cpr = rp.recursivelyMapDialogRule(gl_da_clarification_utterance_present, da_request_dm)
    if mapping_cpa != None:
        mapping = mapping_cpa
    if mapping_cpr != None:
        mapping = mapping_cpr
    if mapping != None:
        clarification_item_type = mapping.get('1')
        last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
        da_list = last_self_utterance_tup[2]
        segment_names = findSegmentNameForDialogActs(da_list)
        print 'segment_names: ' + str(segment_names)

        if len(segment_names) == 1 and segment_names[0] == clarification_item_type:
            return [gl_da_affirmation_yes]
        #generate correction, 'no, [six five zero] is the [exchange]'
        elif len(segment_names) == 1:
            digit_value_list = collectDataValuesFromDialogActs(da_list)
            digit_value_da = synthesizeLogicalFormForDigitOrDigitSequence(digit_value_list)

            da_str_inform_item_type = gl_str_da_inform_item_type.replace('$1', segment_names[0])
            da_inform_item_type = rp.parseDialogActFromString(da_str_inform_item_type)
            return [gl_da_correction_dm_negation, digit_value_da, da_inform_item_type]

        return [da_request_dm]

                                                  

#da_list is a list of DialogActs
#Returns a list of data segment names (e.g. 'area-code') for the agent's self_dialog_model.data_model 
#that match the digits
def findSegmentNameForDialogActs(da_list):
    global gl_agent
    test_digit_value_list = collectDataValuesFromDialogActs(da_list)
    matching_segment_name_list = []

    for segment_name in gl_agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = gl_agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]

        print 'testing segment_name ' + segment_name
        test_digit_i = 0
        match_p = True
        for segment_i in range(segment_start_index, segment_end_index+1):
            segment_digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[segment_i]
            segment_data_value_tuple = segment_digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            segment_data_value = segment_data_value_tuple[0]
            if test_digit_i >= len(test_digit_value_list):
                match_p = False
                break
            test_digit_value = test_digit_value_list[test_digit_i]
            if segment_data_value != test_digit_value:
                print 'XX segment_data_value ' + segment_data_value + ' != test_digit_value ' + test_digit_value
                match_p = False
                break
            elif segment_i == segment_end_index:
                if test_digit_i+1 < len(test_digit_value_list):
                    print 'test_digit_i ' + str(test_digit_i) + ' < ' + 'len(test_digit_value_list): ' + str(len(test_digit_value_list))
                    match_p = False
                break
            test_digit_i += 1
        if match_p:
            matching_segment_name_list.append(segment_name)
    return matching_segment_name_list
        

    

    
#Runs through a list of DialogActs that might include InformTopicInfo(ItemValue( Digit or DigitSequence.
#Collects up all of the digits in order and returns them in a list.
def collectDataValuesFromDialogActs(da_list):
    print 'collectDataValues: ' + str(da_list)
    for da in da_list:
        print da.getPrintString()
    digit_value_list = []
    for da in da_list:
        da_print_string = da.getPrintString()
        ds_index = da_print_string.find('ItemValue(DigitSequence(')
        if ds_index >= 0:
            start_index = ds_index + len('ItemValue(DigitSequence(')
            rp_index = da_print_string.find(')', start_index)
            digit_value_list.extend(extractItemsFromCommaSeparatedListString(da_print_string[start_index:rp_index]))
            continue
        d_index = da_print_string.find('ItemValue(Digit(')
        if d_index >= 0:
            start_index = d_index + len('ItemValue(Digit(')
            rp_index = da_print_string.find(')', start_index)
            digit_value_list.append(da_print_string[start_index:rp_index])
            continue
    return digit_value_list




    


#This sets the self and partner data_index_pointer to the start of the segment
#Returns a list of dialog-acts which could be empty.
def handleSendSegmentChunkNameAndData(segment_chunk_name):
    global gl_agent
    chunk_indices = gl_agent.self_dialog_model.data_model.data_indices.get(segment_chunk_name)
    #This decision to reset belief in partner data_model now made by the caller.
    ##If partner is asking for a chunk, reset belief in partner data_model for this segment as unknown
    #for i in range(chunk_indices[0], chunk_indices[1] + 1):
    #    data_index_pointer = gl_10_digit_index_list[i]
    #    gl_agent.partner_dialog_model.data_model.setNthPhoneNumberDigit(data_index_pointer, '?', 1.0)

    chunk_start_index = chunk_indices[0]
    gl_agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(chunk_start_index)
    gl_agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(chunk_start_index)
    str_da_say_item_type = gl_str_da_say_item_type.replace('$1', segment_chunk_name)
    da_say_item_type = rp.parseDialogActFromString(str_da_say_item_type)
    ret = [da_say_item_type]

    data_value_list = []
    for digit_i in range(chunk_indices[0], chunk_indices[1]+1):
        digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)

    digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
    if digit_sequence_lf != None:
        ret.append(digit_sequence_lf)
        return ret
    else:
        return []




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



#The confidence the data sender places in the belief that the data receiver has the
#correct data, when the receiver does not check-confirm the data value, but only 
#issues a confirm-affirmation (e.g. "yes", "okay").
#This might be set according to estimate of channel quality and receiver understanding 
#reliability
gl_confidence_for_confirm_affirmation_of_data_value = .8


#ConfirmDialogManagement
#Reiterate or affirm/disaffirm dialog management protocol state.
#
#[Also used if the speaker is the information recipient but is taking authoritative
# stance about and responsibility for their topic belief.]
def handleConfirmDialogManagement(da_list):
    da_confirm_dm = da_list[0]

    #printAgentBeliefs(False)

    #handle affirmation continuer: 'User: okay or User: yes
    #right now, we don't have any other kind of ConfirmDialogManagement
    mapping = rp.recursivelyMapDialogRule(gl_da_affirmation, da_confirm_dm)
    if mapping == None:
        return
    if gl_agent.send_receive_role == 'banter':
        return handleConfirmDialogManagement_BanterRole(da_list)

    if gl_agent.send_receive_role == 'send':
        return handleConfirmDialogManagement_SendRole(da_list)

    if gl_agent.send_receive_role == 'receive':
        return handleConfirmDialogManagement_ReceiveRole(da_list)


#When the data topic info sender receive a ConfirmDialogManagement DialogAct from the topic info recipient.
def handleConfirmDialogManagement_SendRole(da_list):
    print 'handleConfirmDialogManagement_SendRole'
    for da in da_list:
        print '   ' + da.getPrintString()

    # here we need to detect any number in the da_list
    #if there is one, then strip off the initial confirm before it updateBeliefInPartnerDataState because
    #the number overrides the general affirmation and gets specific about what is being confirmed
        
    #In case the ConfirmDialogManagement DialogAct is compounded with other DialogActs on this turn,
    #strip out the ConfirmDialogManagement DialogActs and call generateResponseToInputDialog again recursively.
    #Strip out all affirmations from the list of remaining DialogActs to avoid the mistake of calling
    #updateBeliefInPartner...on this partner turn, when the turn also contains details like a digit
    #being confirmed.
    da_list_no_confirm = []
    for da in da_list:
        str_da = da.getPrintString();
        if str_da.find('ConfirmDialogManagement') < 0:
            da_list_no_confirm.append(da)
    print 'len(da_list_no_confirm): ' + str(len(da_list_no_confirm)) + ' len(da_list): ' + str(len(da_list))
    if len(da_list_no_confirm) > 0:
        return generateResponseToInputDialog(da_list_no_confirm)

    #advances the partner's index pointer
    print ' AB'
    pointer_advance_count = updateBeliefInPartnerDataStateBasedOnMostRecentTopicData(gl_confidence_for_confirm_affirmation_of_data_value) 
    print 'after updateBeliefIn... pointer_advance_count is ' + str(pointer_advance_count)
    #this causes an error on RequestTopicInfo(request-confirmation) if partner asks about 
    #e.g. one digit when self said three
    #pointer_advance_count = updateBeliefInPartnerDataStateBasedOnLastDataSent(gl_confidence_for_confirm_affirmation_of_data_value)  

    middle_or_at_end = advanceSelfIndexPointer(gl_agent, pointer_advance_count)  
    (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()

    if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
            len(self_belief_partner_registers_unknown_digit_indices) == 0:
        gl_agent.setRole('banter')
        return [gl_da_all_done];
    
    #In case the ConfirmDialogManagement DialogAct is compounded with other DialogActs on this turn,
    #call generateResponseToInputDialog again recursively.
    #Strip out all affirmations from the list of remaining DialogActs to avoid the mistake of calling
    #updateBeliefInPartner... above again on this partner turn.
    #This is not really the right way to handle multiple affirmations in an utterance.
    #Really, additional confirmations within the utterance should be doing reinforcement 
    #of the interpretation, not tacking on one after another.
    da_list_remainder = []
    for da in da_list:
        if da.intent != 'ConfirmDialogManagement':
            da_list_remainder.append(da)
    if len(da_list_remainder) > 0:
        return generateResponseToInputDialog(da_list_remainder)

    return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()




def handleConfirmDialogManagement_ReceiveRole(da_list):
    print 'handleConfirmDialogManagement_ReceiveRole'
    for da in da_list:
        print '   ' + da.getPrintString()
    return []



def handleConfirmDialogManagement_BanterRole(da_list):
    for da in da_list:
        print '   ' + da.getPrintString()

    #strip out any confirm DialogActs and pass on the rest to the top level handler
    da_list_no_confirm = []
    for da in da_list:
        str_da = da.getPrintString();
        if str_da.find('ConfirmDialogManagement') < 0:
            da_list_no_confirm.append(da)
    print 'len(da_list_no_confirm): ' + str(len(da_list_no_confirm)) + ' len(da_list): ' + str(len(da_list))
    if len(da_list_no_confirm) > 0:
        return generateResponseToInputDialog(da_list_no_confirm)

    #da_list contained only confirmations, no instructions.
    return [gl_da_misaligned_roles, gl_da_dialog_invitation]

    return None



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

    print 'prepareAndSendNext... self data_index_pointer'
    
    consensus_index_pointer = gl_agent.getConsensusIndexPointer()
    print 'consensus_index_pointer: ' + str(consensus_index_pointer)
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

    #Most of the time, this will just hit on the next chunk of digits to send.
    if consensus_index_pointer != None and consensus_index_pointer == data_index_of_focus:
        return prepareNextDataChunk(gl_agent)

    #$$ Need to do more here to catch mismatch

    #If we drop through to here, then say explicitly what chunk segment we're delivering next
    (segment_name, segment_start_index, chunk_size) = findSegmentNameAndChunkSizeForDataIndex(data_index_of_focus)
    return handleSendSegmentChunkNameAndData(segment_name)

    #This is broken. Do not say the segment_name and then call prepareNextDataChunk because the data chunk size might
    #not be the size of the segment.
    #gl_agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, segment_start_index)
    #gl_agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(gl_10_digit_index_list, segment_start_index)
    #str_da_say_item_type = gl_str_da_say_item_type.replace('$1', segment_name)
    #da_say_item_type = rp.parseDialogActFromString(str_da_say_item_type)
    #ret = [da_say_item_type]
    #ret.extend(prepareNextDataChunk(gl_agent))
    #return ret





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



#target_chunk_size is typically the number of digits sent as check digits by partner.
#This compares with the current chunk size and possibly adjusts it upward or downward.
#We keep the self_dialog_model.protocol_chunck_size aligned with what the partner is indicating.
def possiblyAdjustChunkSize(target_chunk_size):
    print 'possiblyAdjustChunkSize ' + str(target_chunk_size)
    global gl_agent
    (max_value, max_conf), (second_max_value, second_max_conf) =\
                               gl_agent.partner_dialog_model.protocol_chunk_size.getTwoMostDominantValues()

    print str(((max_value, max_conf), (second_max_value, second_max_conf)))
    if target_chunk_size < max_value and target_chunk_size < second_max_value:
        print '...setting to ' + str(target_chunk_size)
        gl_agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInOne(target_chunk_size)
        gl_agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInOne(target_chunk_size)
        
    #hardcode phone number area code and exchange chunk size of 3
    elif target_chunk_size > max_value and max_value < 3:
        print '...setting to 3/4'
        gl_agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)
        gl_agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)
    else:
        print ' leaving as is'





####
#
#Correction
#
#Disaffirm topic information as communicated or dialog management protocol state.
#Assumption that that the recipient's belief confidence is high.
#Used if sender believes the recipient's information is incorrect.
#

#CorrectionTopicInfo
#Reiterate or affirm/disaffirm topic information.
#
def handleCorrectionTopicInfo(da_list):
    print 'handleCorrectionTopicInfo not written yet'

#CorrectionDialogManagement
#Reiterate or affirm/disaffirm topic information.
#
def handleCorrectionDialogManagement(da_list):
    print 'handleCorrectionDialogManagement not written yet'




####
#
#RequestAction
#
#Request robot action or speech
#Used for testing TTS
#

#gl_tts_temp_file = 'C:/tmp/audio/gtts-out.wav'
gl_tts_temp_file = 'C:/tmp/audio/gtts-out.mp3'

#RequestAction
#Reiterate or affirm/disaffirm topic information.
#
def handleRequestAction(da_list):
    da0 = da_list[0]
    print 'handleRequestAction'
    for da in da_list:
        print '    ' + da.getPrintString()

    if da0.getPrintString() == gl_str_da_request_action_echo:
        data_list = collectDataValuesFromDialogActs(da_list)
        
        tts_string = ' '.join(data_list)
        print 'tts_string: ' + tts_string
        ttsSpeakText(tts_string)





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
    agent.self_dialog_model.turn.setAllConfidenceInOne('self')
    #agent believes partner believes it is the agent's turn
    agent.partner_dialog_model.turn.setAllConfidenceInOne('self')

    #initialize agent starting at the first digit
    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(0)   
    #agent believes the partner is also starting at the first digit
    agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(0)

    #initialize with chunk size 3/4
    agent.self_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)     
    #agent believes the partner is ready for chunk size 3/4
    agent.partner_dialog_model.protocol_chunk_size.setAllConfidenceInTwo(3, 4)     

    #initialize with moderate handshaking
    agent.self_dialog_model.protocol_handshaking.setAllConfidenceInOne(3)  
    #agent believes the partner is ready for moderate handshaking
    agent.partner_dialog_model.protocol_handshaking.setAllConfidenceInOne(3)  

    agent.partner_dialog_model.data_model.resetUnknownDigitValues()




def prepareNextDataChunk(agent):
    consensus_index_pointer = agent.getConsensusIndexPointer()
    if consensus_index_pointer == None:
        print 'prepareNextDataChunk encountered misaligned consensus_index_pointer, calling again with tell=True'
        agent.getConsensusIndexPointer(True)
        return [dealWithMisalignedIndexPointer()]

    if consensus_index_pointer >= 10:
        return [gl_da_all_done];


#    chunk_size = -1
#    #try to choose chunk size 3 for area code, 3, for exchange
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

    #choose chunk size to advance to the next segment boundary (area-code, exchange, line-number)

    for segment_name in agent.self_dialog_model.data_model.data_indices.keys():
        segment_indices = agent.self_dialog_model.data_model.data_indices[segment_name]
        segment_start_index = segment_indices[0]
        segment_end_index = segment_indices[1]
        if consensus_index_pointer < segment_start_index:
            continue
        elif consensus_index_pointer > segment_end_index:
            continue
        else:
            chunk_size_to_end_of_segment = segment_end_index - consensus_index_pointer + 1
            break

    pref_chunk_size_options = agent.self_dialog_model.protocol_chunk_size.getTwoMostDominantValues()
    if pref_chunk_size_options[0][0] < chunk_size_to_end_of_segment and pref_chunk_size_options[1][0] < chunk_size_to_end_of_segment:
        print ' aa' 
        chunk_size = pref_chunk_size_options[0][0]
    #No, do not send a chunk that crosses segment boundaries
    #elif pref_chunk_size_options[0][0] > chunk_size_to_end_of_segment
    #    print ' bb'
    #    chunk_size = pref_chunk_size_options[0][0]
    else:
        print ' cc'
        chunk_size = chunk_size_to_end_of_segment
    
    print 'pref_chunk_size_options: ' + str(pref_chunk_size_options) + ' segment_chunk_size: ' + str(chunk_size_to_end_of_segment)
    print 'chunk_size: ' + str(chunk_size) + ' consensus_index_pointer: ' + str(consensus_index_pointer) + ' segment_name: ' + segment_name

    data_value_list = []
    total_num_digits = len(agent.self_dialog_model.data_model.data_beliefs)
    last_index_to_send = consensus_index_pointer + chunk_size
    for digit_i in range(consensus_index_pointer, min(last_index_to_send, total_num_digits)):
        digit_belief = agent.self_dialog_model.data_model.data_beliefs[digit_i]
        data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
        data_value = data_value_tuple[0]
        data_value_list.append(data_value)

    digit_sequence_lf = synthesizeLogicalFormForDigitOrDigitSequence(data_value_list)
    if digit_sequence_lf != None:
        return [digit_sequence_lf]
    else:
        return []
        
#    if len(data_value_list) == 1:
#        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(Digit(' + data_value_list[0] + ')))'
#    else:
#        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(DigitSequence('
#        for data_value in data_value_list:
#            str_digit_sequence_lf += data_value + ','
#
#        #strip off the last comma
#        str_digit_sequence_lf = str_digit_sequence_lf[:len(str_digit_sequence_lf)-1]
#        str_digit_sequence_lf += ')))'
#    
#    digit_sequence_lf = rp.parseDialogActFromString(str_digit_sequence_lf)
#    return [digit_sequence_lf]



#digit_list is a list like ['six', 'five', 'zero')
#This returns a single LogicalForm, either InformTopicInfo(ItemValue(Digit or else InformTopicInfo(ItemValue(DigitSequence
def synthesizeLogicalFormForDigitOrDigitSequence(digit_list):
    if len(digit_list) == 0:
        return None
    elif len(digit_list) == 1:
        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(Digit(' + digit_list[0] + ')))'
    else:
        str_digit_sequence_lf = 'InformTopicInfo(ItemValue(DigitSequence('
        for digit in digit_list:
            str_digit_sequence_lf += digit + ','

        #strip off the last comma
        str_digit_sequence_lf = str_digit_sequence_lf[:len(str_digit_sequence_lf)-1]
        str_digit_sequence_lf += ')))'
    
    digit_sequence_lf = rp.parseDialogActFromString(str_digit_sequence_lf)
    return digit_sequence_lf





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

    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(next_data_index_pointer_loc)
    agent.partner_dialog_model.data_index_pointer.setAllConfidenceInOne(next_data_index_pointer_loc)

    print 'adancing index pointer by chunk_size: ' + str(chunk_size) + ' to ' + str(consensus_index_pointer)
#
#####



gl_10_digit_index_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

#Turn is absolute, 'self' refers to the agent.self and 'partner' refers to agent.partner.
#This is the case both for agent.self_data_model and agent.partner_data_model
#So gl_turn_mnb will be [0, 0, 1] if partner thinks it is their turn.
gl_turn_mnb = ['self', 'either', 'partner']

#Degrees of handshaking aggressiveness, least = 1, most = 5
gl_handshake_level_mnb = [1, 2, 3, 4, 5]

gl_chunk_size_mnb = [1, 2, 3, 4, 10]


#return 'middle' or 'at-end'
def advanceSelfIndexPointer(agent, pointer_advance_count):
    self_dm = agent.self_dialog_model
    self_index_pointer = self_dm.data_index_pointer.getDominantValue()

    #if self_index_pointer >= 9:
    #    return 'done-already'
    
    next_data_index_pointer_loc = self_index_pointer + pointer_advance_count
    if next_data_index_pointer_loc >= len(gl_10_digit_index_list):
        agent.self_dialog_model.data_index_pointer.setEquallyDistributed()
        return 'at-end'
        
    agent.self_dialog_model.data_index_pointer.setAllConfidenceInOne(next_data_index_pointer_loc)
    print 'advancing self index pointer by : ' + str(pointer_advance_count) + ' to ' + str(next_data_index_pointer_loc)
    return 'middle'








#simple version:
#retrieve data values sent in last single self turn,
#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#A more advanced version will consider the belief in the partner's expected chunk size, and 
#account for the fact that the partner may be confused if the number of digits sent does not
#match their expected chunk size.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnLastDataSent(update_digit_prob):
    global gl_turn_history
    last_self_data_sent = None
    for turn_i in range(0, len(gl_turn_history)):
        turn_tup = gl_turn_history[turn_i]
        if turn_tup[1] == 'partner':
            continue
        turn_da_list = turn_tup[2]
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
        return updateBeliefInPartnerDataStateBasedOnDataValues(last_self_data_sent, update_digit_prob)
    else:
        return 0





#retrieve data values last discussed and stored as DialogActs in gl_most_recent_data_topic_da_list
#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#A more advanced version will consider the belief in the partner's expected chunk size, and 
#account for the fact that the partner may be confused if the number of digits sent does not
#match their expected chunk size.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnMostRecentTopicData(update_digit_prob):
    global gl_most_recent_data_topic_da_list

    print 'updateBeliefInPartnerDataStateBasedOnMostRecentTopicData()'
    print str(len(gl_most_recent_data_topic_da_list)) + ' das in gl_most_recent_data_topic_da_list: '
    for da in gl_most_recent_data_topic_da_list:
        print '  ' + da.getPrintString()

    if len(gl_most_recent_data_topic_da_list) == 0:
        return 0
    return updateBeliefInPartnerDataStateBasedOnDataValues(gl_most_recent_data_topic_da_list, update_digit_prob)



    

#da_list probably consists of a single DialogAct, either 
#  InformTopicInfo(ItemValue(Digit(x1)))  or else
#  InformTopicInfo(ItemValue(DigitSequence(x1, x2, x3)))  
#where x1 will be a string digit value, e.g. 'one'
#The probability of this value is set to update_digit_prob, the remaining probability is set to ?,
#so update_digit_prob can be different for a check vs simple affirmation reply.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateBasedOnDataValues(da_list, update_digit_prob):
    #print 'updateBeliefInPartnerDataStateBasedOnDataValues(da_list)'
    for da in da_list:
        da_print_string = da.getPrintString()
    #    print 'da: ' + da_print_string
        ds_index = da_print_string.find('ItemValue(DigitSequence(')
        if ds_index >= 0:
            start_index = ds_index + len('ItemValue(DigitSequence(')
            rp_index = da_print_string.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(da_print_string[start_index:rp_index])
            print 'updateBelief...digit_value_list: ' + str(digit_value_list)
            return updateBeliefInPartnerDataStateForDigitValueList(digit_value_list, update_digit_prob)
        d_index = da_print_string.find('ItemValue(Digit(')
        if d_index >= 0:
            start_index = d_index + len('ItemValue(Digit(')
            rp_index = da_print_string.find(')', start_index)
            digit_value = da_print_string[start_index:rp_index]
            print 'updateBelief...digit_value: ' + str(digit_value)
            return updateBeliefInPartnerDataStateForDigitValueList([digit_value], update_digit_prob)
        print 'updateBeliefInPartnerDataStateBasedOnDataValues() identified no digits to update for da: ' + da_print_string
    return 0
    


#iterate update belief in partner data values at belief in their index pointer loc, 
#        then advance belief in their index pointer loc
#str_digit_list is a list of strings, e.g. ['one', 'six'...]
#The probability of this value is set to update_digit_prob, the remaining probability is set to ?,
#so update_digit_prob can be different for a check vs simple affirmation reply.
#Returns the number of digits by which the partner's index pointer was advanced
def updateBeliefInPartnerDataStateForDigitValueList(str_digit_value_list, update_digit_prob):
    #print 'updateBeliefInPartnerDataStateForDigitList(' + str(str_digit_value_list) + ')'
    partner_dm = gl_agent.partner_dialog_model
    partner_index_pointer_advance_count = 0

    for digit_value in str_digit_value_list:
        partner_index_pointer_value = partner_dm.data_index_pointer.getDominantValue()
        partner_dm.data_model.setNthPhoneNumberDigit(partner_index_pointer_value, digit_value, update_digit_prob)
        partner_index_pointer_value += 1
        partner_index_pointer_advance_count += 1
        partner_dm.data_index_pointer.setAllConfidenceInOne(partner_index_pointer_value)

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
        if partner_belief_tup[1] > gl_threshold_on_belief_partner_has_wrong_value:
            print 'compareDataModelBeliefs: ' + str(i) + ' self: ' + str(self_belief_tup) + ' partner: ' + str(partner_belief_tup)
            digits_out_of_agreement.append(i)

    return (digits_out_of_agreement, digits_self_believes_partner_registers_unknown)




#partner_digit_word_sequence is a sequence of data value words sent as check data by partner. These could include '?'
#last_sent_digit_value_list is a sequence of data value words most recently sent by self.
#This attempts to register the partner_digit_word_sequence with last_sent_digit_value_list, and also with 
#the digit sequence in gl_agent.self_dialog_model.data_model.
#Examples: 
#       sent   six five zero
#      check   six five zero
#
#       sent   six five zero
#      check   six five
#
#       sent   six five zero
#      check   six 
#
#       sent   six five zero
#      check       five zero
#
#       sent   six five zero
#      check       five
#
#       sent   six five zero
#      check            zero
#
#       sent   six five zero
#      check   six      zero
#
#       sent   six five zero
#      check   eight
#
#       sent   six five zero
#      check       four zero
#
#      model   six five zero  six three nine one two one two
#       sent   six five zero
#      check   six five zero  six three nine
#
#      model   six five zero  six three nine one two one two
#       sent   six five zero
#      check                  six three nine
#
#       sent   three three two
#      check   three
#
#       sent   three three two
#      check   three three
#
#       sent   three three two
#      check         three two
#
#       sent   three three two
#      check   three seven
#
#       sent   three three two
#      check   three two   two
#
#       sent   three two three
#      check   three 
#
#       sent   three three three
#      check   three three
#
#       sent   three three three
#      check   three 
#
#       sent   eight two seven
#      check   four  two
#
#       sent   eight two seven
#      check         two six
#
#       sent   eight two seven
#      check   nine  one
#
#       sent   eight two seven
#      check   eight ?
#
#       sent   eight two seven
#      check   eight ?   seven
#
#       sent   eight two seven
#      check             seven ?
#
#       sent   eight two seven
#      check   nine 
#
#      model   six five zero  nine three nine one two one two
#       sent   six five zero
#      check   nine
#
#      model   six five zero  nine three nine one two one two
#       sent   six five zero
#      check   nine three
#
#
#previously: 
#       sent   six five
#      check   six five
#this turn:
#       sent            zero
#      check            zero
#
#      model   six five zero  six three nine one two one two
#       sent            zero
#      check   six five zero
#
#      model   six five zero  six three nine one two one two
#       sent            zero
#      check       five zero
#
#       sent            zero
#      check       five eight
#
#       sent            zero
#      check            eight
#
#      model   six five zero  six three nine one two one two
#       sent            zero
#      check       four zero
#   
#Cases:
#-If len(partner_check_digit_sequence) <= len(last_said_digit_list), then
# register first digit to first digit.
# -If all digits match, then return the number of matching digits
# -If any digits don't match, then return 0 for the number of successful matches.
#
#-If len(partner_check_digit_sequence) > len(last_said_digit_list), then
# register last digit to last digit.
# If all digits match, then check the remaining preceeding digits of partner_check_digit_sequence
# with the correct data model.  If these all match, then return len(last_said_digit_list) to
# to show that all digits just said were gotten correctly and put correctly in context.
#
#(This not implemented yet:
#-If num matching return is 0, then finally check to see if the partner_check_digits match
# the following data values.  If so, then in the second position of the tuple return the
# name of the next segment.)
#
#Normally, self_data_index_pointer will point a the first last_said_digit
#
#Returns a tuple (num_digits_matched, name_of_next_segment_if_fully_matched)
#If a full match of partner_check_digit_sequence is not achieved, then this returns 
#(0, None).   
#This is still lacking in that it does not detect a match to data not included in the last_said_digit_list.
#
def registerCheckDataWithLastSaidDataAndDataModel(partner_check_digit_sequence, last_said_digit_list, self_data_index_pointer):
    global gl_agent

    print 'registerCheck... partner: ' + str(partner_check_digit_sequence) + ' last_said: ' + str(last_said_digit_list) + ' self_data_index_pointer: ' + str(self_data_index_pointer)
    match_p = True
    if len(partner_check_digit_sequence) <= len(last_said_digit_list):
        i = 0
        while i < len(partner_check_digit_sequence):
            if partner_check_digit_sequence[i] != last_said_digit_list[i]:
                match_p = False
                break
            i += 1
        if match_p == True:
            return (i, None)

    elif len(partner_check_digit_sequence) > len(last_said_digit_list):
        i_last_said = len(last_said_digit_list)-1
        i_partner =  len(partner_check_digit_sequence)-1
        while i_last_said >= 0:
            print 'a1: i_last_said: ' + str(i_last_said) + ' i_partner: ' + str(i_partner)
            if partner_check_digit_sequence[i_partner] != last_said_digit_list[i_last_said]:
                print 'mismatch: ' + partner_check_digit_sequence[i_partner] + ' != ' + last_said_digit_list[i_last_said]
                match_p = False
                break
            i_partner -= 1
            i_last_said -= 1
        if i_partner > self_data_index_pointer:
            print 'b1 i_partner: ' + str(i_partner) + ' > self_data_index_pointer: ' + str(self_data_index_pointer)
            match_p = False

        sdip = self_data_index_pointer-1
        print ' i_partner: ' + str(i_partner) + ' i_last_said: ' + str(i_last_said) + ' sdip: ' + str(sdip)
        if match_p == True:
            while i_partner >= 0:
                self_digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[sdip]
                self_data_value_tuple = self_digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
                self_data_value = self_data_value_tuple[0]
                if partner_check_digit_sequence[i_partner] != self_data_value:
                    print ' c1 partner_check_digit_sequence[i_partner]: ' + partner_check_digit_sequence[i_partner] + ' != self_data_value: ' + self_data_value
                    match_p = False
                    break
                i_partner -= 1
                sdip -= 1
        if match_p == True:
            return (len(last_said_digit_list), None)

    #drop through to here if a match failure, check to see if the partner_check_digit_sequence matches
    #another segment
    #This not written yet
    print 'dd drop through'
    return (0, None)








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
    


#10 time ticks per second
gl_time_tick_ms = 100

#how much to adjust turn confidence toward self, per time tick
#10 time ticks per second * .01 = 10 seconds to move turn all the way to self
gl_time_tick_turn_delta = .01


#If self's turn confidence gets to this value after waiting for partner's response,
#then take the initiative and say something.
#This is very crude, because the propensity to say something should depend on whether
#self has something to say or not.
gl_wait_turn_conf_threshold = .6

###                                                                  ###
### NOTE: This is called in a different thread from the main thread! ###
###                                                                  ###
def handleTimingTick():
    global gl_agent
    if gl_agent == None:
        return
    gl_agent.adjustTurnTowardSelf(gl_time_tick_turn_delta)
    #print 'self turn confidence: ' + str(gl_agent.self_dialog_model.getTurnConfidence('self'))

    if gl_agent.self_dialog_model.getTurnConfidence('self') > gl_wait_turn_conf_threshold:
        issueOutputAfterWaitTimeout()



#This gets triggered after self's turn confidence exceeds a threshold after waiting for partner to
#execute their turn.
#This will be called on a different thread from the main thread, so beware simultaneous
#access of the data values.
def issueOutputAfterWaitTimeout():
    global gl_dialog_act_queue

    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
    if last_self_utterance_tup == None:
        return
    da_list = last_self_utterance_tup[2]
    last_self_utterance_contains_inform_digits_p = False
    for da in da_list:
        str_da = da.getPrintString()
        if str_da.find('InformTopicInfo(ItemValue(Digit') == 0:
            last_self_utterance_contains_inform_digits_p = True


    #print 'last_self_utterance_contains_inform_digits_p: ' + str(last_self_utterance_contains_inform_digits_p)
    output_da_list = None
    synthesized_confirm_da_list = [gl_da_affirmation_okay]
    if last_self_utterance_contains_inform_digits_p == True:
        gl_dialog_act_queue.append(('Timeout', synthesized_confirm_da_list))
        
        




gl_wait_timer = None


class WaitTimer():
    def __init__(self, interval_msec, callout_function):
        self.running_p = True
        self.timer_thread_id = thread.start_new_thread(self.timer_thread_function, (interval_msec, callout_function))

    def timer_thread_function(self, interval_msec, callout_function):
        interval_sec = interval_msec/1000.0
        while self.running_p:
            #print 'tick'
            callout_function()
            time.sleep(interval_sec)

    def stopTimer(self):
        self.running_p = False
        print ' timer should now be stopped'


def createAndStartWaitTimer(interval_msec):
    global gl_wait_timer
    if gl_wait_timer == None:
        gl_wait_timer = WaitTimer(interval_msec, handleTimingTick)

def stopTimer():
    global gl_wait_timer
    if gl_wait_timer == None:
        print 'no timer to stop'
        return
    gl_wait_timer.stopTimer()
    gl_wait_timer = None




#
#
###############################################################################


###############################################################################
#
#ASR and TTS
#


######################################
#
#ASR Automatic Speech Recognition
#
#Using the SpeechRecognition package
#https://pypi.python.org/pypi/SpeechRecognition/
#

#This borrows from 
#Python/Lib/site-packages/speech_recognition/__main__

gl_speech_recognizer = None
gl_microphone = None

gl_energy_threshold = 100

def setSpeechEnergyThreshold(val):
    gl_energy_threshold = val


#The speech_recognizer sample demo uses dynamic adjustment of mic energy threshold.
#I found this not to work very well, so we pass in an energy threshold
def initializeASR(energy_threshold):
    global gl_speech_recognizer
    global gl_microphone
    global gl_energy_threshold

    gl_speech_recognizer = sr.Recognizer()
    gl_microphone = sr.Microphone()

    #The speech_recognizer sample demo uses dynamic adjustment of mic energy threshold.
    #I found this not to work very well.
    print("Calibrating background mic energy, a moment of silence please for this")
    with gl_microphone as source: gl_speech_recognizer.adjust_for_ambient_noise(source)
    print("possibly recommending an energy_threshold of {}".format(gl_speech_recognizer.energy_threshold))

    gl_speech_recognizer.dynamic_energy_threshold = False
    gl_speech_recognizer.energy_threshold = gl_energy_threshold
    gl_speech_recognizer.pause_threshold = .3
    gl_speech_recognizer.non_speaking_duration = min(gl_speech_recognizer.non_speaking_duration,\
                                                         gl_speech_recognizer.pause_threshold)
    print("Recognizer pause_threhsold is now " + str(gl_speech_recognizer.pause_threshold))




#When speech is detected and recognized, callback_function is called with the recognized text 
#string is sent as the function argument.
class SpeechRunner():
    def __init__(self, callback_function):
        self.stop_p = False
        self.speechrunner_thread_id = thread.start_new_thread(self.speech_runner_thread_function, (callback_function,))

    def speech_runner_thread_function(self, callback_function):
        global gl_microphone
        global gl_speech_recognizer
        global gl_speech_runner_running_p
        global gl_speech_runner

        print 'Entering speech_runner_thread_function'

        while True and gl_speech_runner != None:
            print("Say something!")
            #this will block while it waits for input
            #http://stackoverflow.com/questions/11195140/python-break-or-exit-out-of-with-statement
            with gl_microphone as source: audio = gl_speech_recognizer.listen(source)

            #In case this SpeechRecognizer has been terminated while listening


            #if self.running_p == False:
            #    print 'got audio but this SpeechRecognizer is terminated'
            #    return

            print("Got it! Now to recognize it..." + str(self.stop_p))
            try:
                if self.stop_p:
                    print 'Quitting out of speech_runner_thread_function'
                    gl_speech_runner = None
                    return

                if audio == None:
                    print 'audio is None but we didnt quit out?'
                    gl_speech_runner = None
                    return

                # recognize speech using Google Speech Recognition
                value = gl_speech_recognizer.recognize_google(audio)



                # we need some special handling here to correctly print unicode characters to standard output
                if str is bytes: # this version of Python uses bytes for strings (Python 2)
                    the_text = u"{}".format(value).encode("utf-8")
                    #print(u"You said {}".format(value).encode("utf-8"))
                else: # this version of Python uses unicode for strings (Python 3+)
                    the_text = "{}".format(value)
                    #print("You said {}".format(value))
                print 'You said ' + the_text
                the_text = spellOutDigits(the_text)

                #The speech might have been picked up while pause was set
                #if gl_speech_runner_paused_p == True:
                #    print 'something was recognized while we speech recognition was supposed to be paused: '
                #    print 'the_text: ' + the_text
                #else:
                #    print 'the_text: ' + the_text
                #    callback_function(the_text)
                callback_function(the_text)

            except sr.UnknownValueError:
                print("Oops! Didn't catch that")
            except sr.RequestError as e:
                print("Uh oh! Couldn't request results from Google Speech Recognition service; {0}".format(e))

        print 'Exiting speech_runner_thread_function'
        gl_speech_runner = None
    
    def stop(self):
        global gl_speech_recognizer
        self.stop_p = True
        gl_speech_recognizer.stopListening()
        print ' speech_runner stop issued'

#    def start(self):
#        self.running_p = True
#        print ' speech_runner should now be started'


gl_speech_runner = None

def startNewSpeechRunner():
    print 'startNewSpeechRunner'
    global gl_speech_runner
    if gl_speech_runner != None:
        print '  calling gl_speech_runner.stop()'
        gl_speech_runner.stop()
    count = 0
    while gl_speech_runner != None:
        count += 1
        if count > 10000:
            print 'timeout waiting for gl_speech_runner_to_stop'
            break
        time.sleep(.005)
    print 'startNewSpeechRunner timeout count: ' + str(count)
    if gl_speech_runner != None:
        print 'could not start a new speech runner because the old one has not stopped'
        return
    gl_speech_runner = SpeechRunner(handleSpeechInput)


#def startNewSpeechRunner():
#    global gl_speech_runner
#    if gl_speech_runner == None:
#        gl_speech_runner = SpeechRunner(handleSpeechInput)
#    gl_speech_runner.start()


def stopSpeechRunner():
    global gl_speech_runner
    if gl_speech_runner == None:
        print 'no speech_runner to stop'
        return
    gl_speech_runner.stop()



#def pauseSpeechRunner():
#    global gl_speech_runner
#    global gl_speech_runner_paused_p
#    if gl_speech_runner == None:
#        print 'no speech_runner to pause'
#        return
#    gl_speech_runner.stop()
#    gl_speech_runner_paused_p = True


#def resumeSpeechRunner():
#    global gl_speech_runner
#    global gl_speech_runner_paused_p
#    if gl_speech_runner == None:
#        print 'no speech_runner to resume'
#        return
#    gl_speech_runner.start()
#    gl_speech_runner_paused_p = False




#ASR normally returns numerals for digits, we spell them out.
#An isolated "two" is sometimes recognized as 'too'.
#And what else...?
def spellOutDigits(text_string):
    text_string = text_string.replace('0', ' zero ')
    text_string = text_string.replace('1', ' one ')
    text_string = text_string.replace('2', ' two ')
    text_string = text_string.replace('too', ' two ')
    text_string = text_string.replace('3', ' three ')
    text_string = text_string.replace('4', ' four ')
    text_string = text_string.replace('5', ' five ')
    text_string = text_string.replace('6', ' six ')
    text_string = text_string.replace('7', ' seven ')
    text_string = text_string.replace('8', ' eight ')
    text_string = text_string.replace('9', ' nine ')
    return text_string








#
#
######################################

######################################
#
#TTS Text to Speech
#
#Using the gTTS package 
#https://pypi.python.org/pypi/gTTS
#


def ttsSpeakText(tts_string):
    global gl_tts_temp_file

    tts = gTTS(text=tts_string, lang='en')
    tts.save(gl_tts_temp_file)

    stopSpeechRunner()
    print 'playMP3 start'
    playMP3(gl_tts_temp_file)
    print 'playMP3 done'
    startNewSpeechRunner()



#This is to play an mp3 file.
#It only works on Windows.  We'll have to figure out something else
#for other platforms.
#
#https://lawlessguy.wordpress.com/2016/02/10/play-mp3-files-with-python-windows/
# Copyright (c) 2011 by James K. Lawless
# jimbo@radiks.net http://www.mailsend-online.com
# License: MIT / X11
# See: http://www.mailsend-online.com/license.php
# for full license details.
 
from ctypes import *;
 
winmm = windll.winmm
 
def mciSend(s):
   i=winmm.mciSendStringA(s,0,0,0)
   if i<>0:
      print "Error %d in mciSendString %s" % ( i, s )
 
def playMP3(mp3Name):
   mciSend("Close All")
   mciSend("Open \"%s\" Type MPEGVideo Alias theMP3" % mp3Name)
   mciSend("Play theMP3 Wait")
   mciSend("Close theMP3")
 


#But guess what, google tts apparenly only outputs an mp3 file, not a wav file.
#http://stackoverflow.com/questions/6951046/pyaudio-help-play-a-file
def playWavFile(wav_filepath):

    # length of data to read.
    play_chunk_size = 1024
    

    # open the file for reading.
    wf = wave.open(wav_filepath, 'rb')

    # create an audio object
    p = pyaudio.PyAudio()

    # open stream based on the wave object which has been input.
    stream = p.open(format =
                    p.get_format_from_width(wf.getsampwidth()),
                    channels = wf.getnchannels(),
                    rate = wf.getframerate(),
                    output = True)

    # read data (based on the play_chunk_size)
    data = wf.readframes(play_chunk_size)

    # play stream (looping from beginning of file to the end)
    while data != '':
        # writing to the stream is what *actually* plays the sound.
        stream.write(data)
        data = wf.readframes(play_chunk_size)

    # cleanup stuff.
    stream.close()    
    p.terminate()


#
#
######################################
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
    #print 'extractItems...l1: ' + str(l1)
    for item in l1:
        item = item.strip()
        #print ' item: ' + item
        str_item_list.append(item)
    return str_item_list
    


gl_transcript_filepath = 'C:/temp/da-transcript.text'
gl_transcript_file = None


def openTranscriptFile(filepath=gl_transcript_filepath):
    global gl_transcript_file
    gl_transcript_file = open(filepath, 'w')

def writeToTranscriptFile(text_string):
    global gl_transcript_file
    gl_transcript_file.write(text_string + '\n')

def closeTranscriptFile():
    global gl_transcript_file
    gl_transcript_file.close()




                        

#
#
###############################################################################



###############################################################################
#
#archives
#





#For agent send role, handle InformTopicInfo of the following kinds
#(DialogActs coming from information recipient partner):
#  - partner check-confirming digit values only (CheckTopicInfo)
#    In this case, agent surmises that the partner's belief in the index pointer has advanced
#    It is possible the partner could submit digit values that are not correct reiteration
#    of the chunck just sent, but align with a different part of the number, e.g. self
#    issuing an area code and partner responding with the correct exchange.  So this function 
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
# This is old, being replaced by a version that tries to align the partner's check digit 
#sequence with the correct self digit sequence, as a better way to infer partner's
#data index pointer.
def handleInformTopicInfo_SendRole_old(da_list):
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

    #print 'handleInformTopicInfo '
    #printAgentBeliefs()

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

        #This applies to an isolated 'what?' which we intend to have substituted for a digit value so
        #is indicative of confusion
        #But the danger is that 'what' said with other words will be interpreted as confusion when it is not,
        #and the system speaks 'I'll repeat that' when they really shouldn't.
        elif str_da_inform_td == gl_str_da_what:
            #partner indicates confusion so we surmise they have not advanced their index pointer with this data chunk.
            #So reset the tentative_partner_index_pointer.
            temp_digit_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()
            partner_expresses_confusion_p = True

    if partner_expresses_confusion_p:
        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret = [gl_da_inform_dm_repeat_intention]
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret

    elif check_matches_last_chunk_p == False:
        possiblyAdjustChunkSize(len(partner_digit_word_sequence))
        ret = [gl_da_correction_topic_info]
        #Since there was no advance, this will send the last data chunk again.
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret

    #all good, we have received from the partner a correct check of the last chunk of digits sent
    else:
        possiblyAdjustChunkSize(len(partner_digit_word_sequence))
        #1.0 is full confidence that the partner's data belief is as self heard it
        pointer_advance_count = updateBeliefInPartnerDataStateForDigitValueList(partner_digit_word_sequence, 1.0) 
        
        #print 'after updateBeliefInPartnerDataState...'
        #printAgentBeliefs()
        middle_or_at_end = advanceSelfIndexPointer(gl_agent, pointer_advance_count)  
        print 'after advanceSelfIndexPointer...'
        #printAgentBeliefs()
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()
        print 'self_belief_partner_is wrong...' + str(self_belief_partner_is_wrong_digit_indices) + ' self_belief unknown... ' +\
            str(self_belief_partner_registers_unknown_digit_indices)

        if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
                len(self_belief_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return [gl_da_all_done];

        else:
            return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()

        #return prepareNextDataChunk(gl_agent)
    


#Seems to be leftover from development
def nothingHereChief():
    #Pick off the most straightforward case, where partner echoes the last sent digits correctly
    mismatch_p = False
    for i in range(0, min(len(last_sent_digit_value_list), len(partner_digit_word_sequence))):
        if last_sent_digit_value_list[i] != partner_digit_word_sequence[i]:
            mismatch_p = True
            
    if mismatch_p == False:
        possiblyAdjustChunkSize(len(partner_digit_word_sequence))
        #1.0 is full confidence that the partner's data belief is as self heard it
        pointer_advance_count = updateBeliefInPartnerDataStateForDigitValueList(partner_digit_word_sequence, 1.0) 
        
        #print 'after updateBeliefInPartnerDataState...'
        #printAgentBeliefs()
        middle_or_at_end = advanceSelfIndexPointer(gl_agent, pointer_advance_count)  
        print 'after advanceSelfIndexPointer...'
        #printAgentBeliefs()
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()
        print 'self_belief_partner_is wrong...' + str(self_belief_partner_is_wrong_digit_indices) + ' self_belief unknown... ' +\
            str(self_belief_partner_registers_unknown_digit_indices)

        if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
                len(self_belief_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return [gl_da_all_done];

        else:
            return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()

    #XX TODO: Here do the interesting alignment stuff
    ret = [gl_da_inform_dm_repeat_intention]
    ret.extend(prepareNextDataChunk(gl_agent))
    return ret




#An OrderedMultinomialBelief represents belief distributed between several ordered values.
class OrderedMultinomialBelief_Old():
    def __init__(self):
        self.value_name_confidence_list = None   #each element is a list [value, confidence]
        #A better implementation is probably two lists, a value list and a confidence list,
        #then a value to index map

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

#    def getValueConfidence(self, target_name):
#        target_index
#        return item for item in value_name_confidence if item[0] == target_name

#    #sets the confidence in target_name to new_target_value
#    #then adjusts the confidence in all other values to normalize to 1
#    def setValueConfidenceNormalizeOthers(self, target_name, new_target_value):
#        value_list = [ item[0] for item in value_name_confidence ]
#        conf_list = [ item[1] for item in value_name_confidence ]
#
#        self_conf = self.turn.getValueConfidence('self')[1]
#        new_self_conf = min(1, self_conf + delta)
#        self.turn.setValueConfidenceNormalizeOthers('self', new_self_conf)



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



#For agent send role, handle InformTopicInfo of the following kinds
#(DialogActs coming from information recipient partner):
#  - partner check-confirming digit values only (CheckTopicInfo)
#    In this case, try to align the partner's stated check digits with the self data model
#    in order to infer what digits the partner is checking, some of which they might have
#    checked before.  If alignment is successful and unambiguous, then it allows us to advance
#    the partner index pointer, and set self data index pointer accordingly.
#  - partner check-confirming digit values mixed with an indication of misunderstanding, e.g. what?
#    In this case, place the partner data_index_pointer at the first what?, but send
#    context digits mirroring the sender's
#
#These are InformTopicInfo because we are not currently able to parse input as multiple
#candidate DialogActs with different intents.
#This old before the first section was lifted and renamed, 
#comparePartnerReportedDataAgainstSelfData(da_list),
#so it could be used with handleInformTopicInfo and handleRequestTopicInfo
#
def handleInformTopicInfo_SendRole_Old(da_list):
    global gl_agent

    partner_digit_word_sequence = []

    partner_expresses_confusion_p = False

    print 'handleInformTopicInfo '
    #printAgentBeliefs()

    #could be an interspersing of ItemValue(Digit( and ItemValue(DigitSequence
    for da in da_list:
        str_da = da.getPrintString()
        if str_da.find('InformTopicInfo(ItemValue(Digit(') == 0:
            start_index = len('InformTopicInfo(ItemValue(Digit(')
            rp_index = str_da.find(')', start_index)
            partner_check_digit_value = str_da[start_index:rp_index]
            partner_digit_word_sequence.append(partner_check_digit_value)

        elif str_da.find('InformTopicInfo(ItemValue(DigitSequence(') == 0:
            start_index = len('InformTopicInfo(ItemValue(DigitSequence(')
            rp_index = str_da.find(')', start_index)
            digit_value_list = extractItemsFromCommaSeparatedListString(str_da[start_index:rp_index])
            partner_digit_word_sequence.extend(digit_value_list)

        #This applies to an isolated 'what?' or other non-digit which we intend to have substituted for a digit value so
        #is indicative of confusion
        #But the danger is that 'what' said with other words will be interpreted as confusion when it is not,
        #and the system speaks 'I'll repeat that' when they really shouldn't.
        elif str_da not in gl_digit_list and str_da.find('ConfirmDialogManagement') < 0:
            #partner indicates confusion so we surmise they have not advanced their index pointer with this data chunk.
            #So reset the tentative_partner_index_pointer.
            partner_expresses_confusion_p = True
            #Add ? partner utterance explicitly into the list of digits we heard them say, in order to
            #pinpoint the index pointer for their indicated check-confusion
            partner_digit_word_sequence.append('?')

    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self', [ 'InformTopicInfo' ])
    last_self_utterance_da_list = last_self_utterance_tup[2]
    last_sent_digit_value_list = collectDataValuesFromDialogActs(last_self_utterance_da_list)
    self_data_index_pointer = gl_agent.self_dialog_model.data_index_pointer.getDominantValue()

    #This is an easy out, to be made more sophisticated later
    if partner_expresses_confusion_p:
        #since we haven't advanced the self data index pointer, then actually we are re-sending the 
        #previous chunk.  We could adjust chunk size at this point also.
        ret = [gl_da_inform_dm_repeat_intention]
        ret.extend(prepareNextDataChunk(gl_agent))
        return ret

    print 'last_sent_digit_value_list: ' + str(last_sent_digit_value_list) + ' partner_digit_word_sequence: ' + str(partner_digit_word_sequence)

    #Here try to align partner's check digit sequence with what self has just provided as a partial digit sequence,
    #or else with the context of previously provided values, or even with correct data that has not been provided
    #in this conversation (i.e. if partner knows the phone number already)
    
    #This returns match_count = 0 if the partner_digit_word_sequence contains any errors or an 
    #alignment match to self's data model cannot be found.
    check_match_tup = registerCheckDataWithLastSaidDataAndDataModel(partner_digit_word_sequence, last_sent_digit_value_list, self_data_index_pointer)

    match_count = check_match_tup[0]
    print 'match_count: ' + str(match_count)
    
    #Only if check-confirm match was validated against self's belief model, update self's model
    #for what partner believes about the data.
    if match_count > 0:       

        possiblyAdjustChunkSize(len(partner_digit_word_sequence))
        #1.0 is full confidence that the partner's data belief is as self heard it
        partner_dm = gl_agent.partner_dialog_model
        newly_matched_digits = []
        for digit_i in range(self_data_index_pointer, self_data_index_pointer + match_count):
            digit_belief = gl_agent.self_dialog_model.data_model.data_beliefs[digit_i]
            data_value_tuple = digit_belief.getHighestConfidenceValue()      #returns a tuple e.g. ('one', .8)
            correct_digit_value = data_value_tuple[0]
            partner_dm.data_model.setNthPhoneNumberDigit(digit_i, correct_digit_value, 1.0)
            partner_index_pointer_value = partner_dm.data_index_pointer.getDominantValue()
            partner_dm.data_index_pointer.setAllConfidenceInOne(digit_i+1)

        #printAgentBeliefs()
        middle_or_at_end = advanceSelfIndexPointer(gl_agent, match_count)  
        print 'after advanceSelfIndexPointer...'
        #printAgentBeliefs()
        (self_belief_partner_is_wrong_digit_indices, self_belief_partner_registers_unknown_digit_indices) = compareDataModelBeliefs()
        #print 'self_belief_partner_is wrong...' + str(self_belief_partner_is_wrong_digit_indices) + ' self_belief unknown... ' +\
        #    str(self_belief_partner_registers_unknown_digit_indices)

        if middle_or_at_end == 'at-end' and len(self_belief_partner_is_wrong_digit_indices) == 0 and\
                len(self_belief_partner_registers_unknown_digit_indices) == 0:
            gl_agent.setRole('banter')
            return [gl_da_all_done];

        else:
            return prepareAndSendNextDataChunkBasedOnDataBeliefComparisonAndIndexPointers()

    ret = [gl_da_inform_dm_repeat_intention]
    ret.extend(prepareNextDataChunk(gl_agent))
    return ret



#this old version works fine for just keyboard input, but adding in a wait timeout
#and then speech gives problems with multithreading.
def loopDialogMain_Old():
    global gl_agent
    global gl_use_speech_p
    input_string = raw_input('Input: ')
    input_string = rp.removePunctuationAndLowerTextCasing(input_string)

    while input_string != 'stop' and input_string != 'quit':
        writeToTranscriptFile('Input: ' + input_string)
        #print '\n' + input_string
        rule_match_list = rp.applyLFRulesToString(input_string)
        if rule_match_list == False:
            print 'no DialogRule matches found'
        else:
            print 'MATCH: ' + str(rule_match_list);
        da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)

        gl_agent.setTurn('self')
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

        #printAgentBeliefs(False)
        str_generated = ' '.join(output_word_list)
        print 'gen: ' + str_generated

        if gl_use_speech_p and len(str_generated) > 0:
            ttsSpeakText(str_generated)
            resetNextTurnBeliefs()

        writeToTranscriptFile('Output: ' + str_generated)
        
        input_string = raw_input('\nInput: ')
        input_string = rp.removePunctuationAndLowerTextCasing(input_string)

    if input_string == 'quit':
        stopTimer()
        stopSpeechRunner()
        closeTranscriptFile()



#This gets triggered after self's turn confidence exceeds a threshold after waiting for partner to
#execute their turn.
#This will be called on a different thread from the main thread, so beware simultaneous
#access of the data values.
def issueOutputAfterWaitTimeout_Old():

    last_self_utterance_tup = fetchLastUtteranceFromTurnHistory('self')
    if last_self_utterance_tup == None:
        return
    da_list = last_self_utterance_tup[2]
    last_self_utterance_contains_inform_digits_p = False
    for da in da_list:
        str_da = da.getPrintString()
        if str_da.find('InformTopicInfo(ItemValue(Digit') == 0:
            last_self_utterance_contains_inform_digits_p = True


    #print 'last_self_utterance_contains_inform_digits_p: ' + str(last_self_utterance_contains_inform_digits_p)
    output_da_list = None
    synthesized_confirm_da_list = [gl_da_affirmation_okay]
    if last_self_utterance_contains_inform_digits_p == True:
        synthesized_confirm_da_list = [gl_da_affirmation_okay]
        output_da_list = generateResponseToInputDialog(synthesized_confirm_da_list)

    #else:
        #output_da_list = [gl_da_check_readiness]

    if output_da_list != None:
        output_word_list = []
        for da in output_da_list:
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

        #printAgentBeliefs(False)
        str_generated = ' '.join(output_word_list)
        print 'gen: ' + str_generated

        if gl_use_speech_p and len(str_generated) > 0:
            ttsSpeakText(str_generated)

        writeToTranscriptFile('Output: ' + str_generated)

        print '\nInput: '


#Treat speech input the same as typed input
def handleSpeechInput_Old(input_string):
    global gl_agent

    writeToTranscriptFile('Input: ' + input_string)

    print 'handleSpeechInput: ' + str(input_string)

    rule_match_list = rp.applyLFRulesToString(input_string)
    if rule_match_list == False:
        print 'no DialogRule matches found'
    else:
        print 'MATCH: ' + str(rule_match_list);
    da_list = rp.parseDialogActsFromRuleMatches(rule_match_list)

    gl_agent.setTurn('self')
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

    #printAgentBeliefs(False)
    str_generated = ' '.join(output_word_list)
    print 'gen: ' + str_generated
    if len(str_generated) > 0:
        ttsSpeakText(str_generated)
        resetNextTurnBeliefs()

    writeToTranscriptFile('Output: ' + str_generated)

