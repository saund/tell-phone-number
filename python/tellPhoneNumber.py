#!/usr/bin/python -tt

#tellPhoneNumber.py is an intial start at a dialog management system to
#transmit structured data between a transmitter and a receiver using human
#conversational dialogue.


import csv
import random
import sys
import copy
import re
import os
import math


#No longer using cdm, we'll have our own Otto-like rule set and write our own string parser here.
##Use the cdm python project under this project organization
##dialog
## cdm
##  python
## tell-phone-number
##  python
#cdm_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..', 'cdm', 'python'))
#
#print 'cdm_path: ' + cdm_path
#sys.path.append(cdm_path)
#
#from patternMatchj import *


#print 'gl_rules_dirpath: ' + gl_rules_dirpath

gl_rules_dirpath = os.path.join(os.getcwd(), '..', 'rules')

#print 'and then... gl_rules_dirpath: ' + gl_rules_dirpath



def loopInput():
    init('tell-phone-number-rules1.txt')
    input_string = raw_input('Input: ')
    while input_string != 'stop' and input_string != 'quit':
        print '\n' + input_string
        res = applyLFRulesToString(input_string)
        if res == False:
            print 'no match'
        else:
            print 'MATCH: ' + str(res);
        input_string = raw_input('\nInput: ')







gl_default_lf_rule_filename = 'tell-phone-number-lf-rules.txt'

#key: first-word-or-category-of-sequence:  value: (rule_rhs, rule_lhs)
#       where rule_rhs is a sequence of words or catgories
#             rule_lhs is a text representation of a DialogAct, which is Intent(LogicalForm)
gl_first_word_string_to_rule_dict = {}

#Word-categories are like in Otto, in terms of variables enclosed by brackets [$1]
#e.g. DigitCat[one] <-> one
#This allows a rule to be:
#InformTD(ItemValue(Digit($1))) <-> {DigitCat[$1]}
#Where the {DigitCat[$1]} allows 'one' to generate the DialogAct:
#InformTD(ItemValue(Digit(one)))

#key:  string: word-category-name[args]    value: list: word-list
#e.g.  'DigitCat[one]'                     [one]
gl_word_wcategory_fw_dict = {}

#value: list: word-list             key:  string: word-category-name[args] 
#e.g.   [one]                       'DigitCat[one]'
gl_word_wcategory_rv_dict = {}

#$$$XX This not completed yet about how to organize Word Categories

#$$ Need to make sure that if a DialogAct rhs starts with a word-category, then
#each first word for that word-category adds this DialogRule to the first-word index.


def initLFRules(lf_rule_filename = gl_default_lf_rule_filename):
    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    print 'tellPhoneNumber LF rules filepath: ' + filepath
    compileStringToLFRuleDict(filepath)



def compileStringToLFRuleDict(filepath):
    file = open(filepath, "rU")
    
    gl_first_word_string_to_rule_dict = {}
    rule_text = ''
    while True:
        text_line = file.readline()
        if not text_line:
            break
        hash_index = text_line.find('#')
        if hash_index == 0:
            continue
        elif hash_index > 0:
            text_line = text_line[0:hash_index]
        backslash_index = text_line.find('\\')
        if backslash_index > 0:
            text_line = text_line[0:backslash_index]
            rule_text += text_line
        else:
            rule_text += text_line
            if len(rule_text) > 1:
                parseAndAddRule(rule_text)
            rule_text = ''
    file.close()
    
    print '\ngl_all_rules:'
    printAllRules()


def parseAndAddRule(rule_text):
    leftarrow_index = rule_text.find('<')
    if leftarrow_index < 0:
        print 'could not find < in rule_text: ' + rule_text
        return
    rightarrow_index = rule_text.find('>')
    if rightarrow_index < 0:
        print 'could not find > in rule_text: ' + rule_text
        return
    lhs = rule_text[0:leftarrow_index]
    lhs = lhs.strip()
    rhs = rule_text[rightarrow_index+1:]
    rhs = rhs.strip()
    rule = (rhs, lhs)
    space_index = rhs.find(' ')
    if space_index > 0:
        first_string_or_category = rhs[0:space_index]
    else:
        first_string_or_category = rhs

    #$$$XX This not completed yet about how to organize Word Categories
    #determine if a DialogRule or else a Word Category
    if lhs.find('['):               #Word Category
        existing_list = gl_first_word_string_to_wcategory_dict.get(first_string_or_category)
        if existing_list == None:
            new_wcategory_list = [rule]
            gl_first_word_string_to_wcategory_dict[first_string_or_category] = new_wcategory_list
        else:
            existing_list.append(rule)

    else:                           #DialogRule
        existing_list = gl_first_word_string_to_rule_dict.get(first_string_or_category)
        if existing_list == None:
            new_rule_list = [rule]
            gl_first_word_string_to_rule_dict[first_string_or_category] = new_rule_list
        else:
            existing_list.append(rule)


def printAllRules():
    for rule_key in gl_first_word_string_to_rule_dict.keys():
        rule = gl_first_word_string_to_rule_dict[rule_key]
        print rule_key + ' : '  + str(rule)




def applyLFRulesToString(input_string):
    word_list = input_string.split()
    word_index = 0;
    
    res = []    #a list of rule fits to the_string: [(DialogAct, start_i, end_i),...]
    while word_index < len(word_list):
        i_word = word_list[word_index]
        possible_rules = gl_first_word_string_to_rule_dict.get(i_word)
        for rule in possible_rules:
            rule_fit = testRuleOnInputWordsAtWordIndex(rule, word_list, i_word)
            if rule_fit != None:
                res.append(rule_fit)
    return res


#This applies all available rules to the word_list starting at i_word.
#rule is  (rule_rhs, rule_lhs)
#       where rule_rhs is a sequence of words or word-catgories
#             rule_lhs is a text representation of a DialogAct
#
#It is assumed that the first word of the rule_rhs matches the i_word of word_list.
#rule_lhs might have arguments like $1 which will get filled in from matches of word-categories
#to the word_list.
#If an element in rule_rhs is enclosed by braces { } then it is a reference to a word-category.
#Then each member of that word-category is looked up and tested against the string starting at
#i_word.  If a match is found, then the variable $1 for that word-category is made available
#for setting the argument value for that variable in the rule_lhs
#
#This returns a list: [ (DialogAct, i_word, i_next_word), ...]
#The DialogAct's arguments will be filled in with values from any Word-Categories that were used
#i_word and i_next_word in the tuple tell what part of the word_list is spanned by the DialogAct.
def testRuleOnInputWordsAtWordIndex(rule, word_list, i_word_start):

    rule_rhs = rule[0]
    arg_index_map = {}    #key: $X where X is an argument indicator, value:  a predicate provided by a word-category
                          #that will substitute for $X in the DialogAct returned (if it matches)
    i_word = i_word_start
    i_rule = 0
    while i_word < len(word_list):
        rule_word_or_word_category = rule_rhs[i_rule]

        #rule_word_or_word_category is either a word or else an indicator of a word-category, like, {DigitCat[$1]}
        if rule_word_or_word_category.find('{') == 0:
            lbr_index = rule_word_or_word_category.find('[')
            word_category_name = rule_word_or_word_category[0:lbr_index]
            word_category = gl_word_category_dict.get(word_category_name)
            if word_category == None:
                print 'testRuleOnInputWordsAtWordIndex() could not find word-category ' + word_category_name
                i_word += 1
                continue
            (num_words_consumed, word_category_arg) = testWordCategoryOnInputWordsAtWordIndex(word_category, word_list, i_word)
            if num_words_consumed > 0:
                lsb_index = rule_word_or_word_category.find('[$')
                rsb_index = rule_word_or_word_category.find(']')
                arg_indicator = rule_word_or_word_category[lsb_index+2:rsb_index]
                arg_index_map[arg_indicator] = word_category_arg
                i_word += num_words_consumed
                i_rule += 1
            else:
                return None
        else:
            if word_list[i_word] == rule_word_or_word_category:
                i_word += 1
                i_rule += 1
            else:
                return None
        if i_word >= len(word_list):
            return None
        #the DialogAct matches
        if i_rule >= len(rule_rhs):
            rule_dialog_act = rule[1]
            lbr_index = rule_dialog_act.find('{$')
            while lbr_index > 0:
                rbr_index =
                $$

            
        
                

        #a rule_word_or_word_category is like,   ((one fine day), DigitCat[$1])
        #where 'one', 'fine', 'day', and 'DigitCat[$1]' are all strings.
        #and the word-category DigitCat includes the mapping,
        #User: DigitCat[one] <-> one



                

            
        
    
    return None
        
        

    








#LogicalForm intents
#
#InformTopicData
#RequestTopicData
#CheckTopicData
#ConfirmTopicData
#
#InformDM    DM = DialogManagement
#RequestDM
#CheckDM
#ConfirmDM
#

class LogicalForm():
    def __init__(self):
        self.intent = ''
        self.type = ''
        self.data = None
        self.string = None


    def getPrintString(self):
        print_string = self.intent + '(' + self.type
        if self.data != None:
            print_string += ', ' + self.data + ')'
        else:
            print_string += ')'
        return print_string



#Returns an Actor that is either a sender ('send') or receiver ('receive') of a telephone number
#that should be ready to engage in dialogue.
def createBasicActor(send_or_receive):
    actor = Actor()
    actor.name = 'computer'
    actor.partner_name = 'person'
    actor.send_receive_role = send_or_receive
    actor.self_dialog_model = initDialogModel('self', send_or_receive)
    actor.partner_dialog_model = initDialogModel('partner', sendReceiveOpposite(send_or_receive))
    return actor




def sendReceiveOpposite(send_or_receive):
    if send_or_receive == 'send':
        return 'receive'
    elif send_or_receive == 'receive':
        return 'send'
    else:
        print 'sendReceiveOpposite() got invalid arg ' + send_or_receive
        return None


class Actor():
    def __init__(self):
        self.name = None
        self.partner_name = None
        self.send_receive_role = None     #'send' or 'receive'
        self.self_dialog_model = None
        self.partner_dialog_model = None


    def setRole(sender_or_receiver, phone_number=None):
        return None

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        pstr = 'Actor: ' + self.name
        pstr += '     partner: ' + self.partner_name + '\n'
        pstr += 'role: ' + self.send_receive_role + '\n\n'
        pstr += self.self_dialog_model.getPrintString() + '\n'
        pstr += self.partner_dialog_model.getPrintString() + '\n'
        return pstr


gl_default_phone_number = '6506371212'

def initDialogModel(self_or_partner, send_or_receive):
    dm = DialogModel()
    dm.model_for = self_or_partner
    dm.data_model = DataModel_USPhoneNumber()
    if send_or_receive == 'send':
        dm.data_model.setPhoneNumber(gl_default_phone_number)
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
            digit = phone_number_string[i]
            self.data_beliefs[i].setValueDefinite(digit)


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



        
        

                        




