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


#Test just the rules in isolated-rules-test.txt
def loopInputTest():
    initLFRules('isolated-rules-test.txt')
    loopInputMain()

    
#Test the rules in gl_default_lf_rule_filename.
#Loop one input and print out the set of DialogActs interpreted
def loopInput():
    initLFRulesIfNecessary()
    loopInputMain()


def loopInputMain():
    input_string = raw_input('Input: ')
    input_string = removePunctuationAndLowerTextCasing(input_string)
    while input_string != 'stop' and input_string != 'quit':
        print '\n' + input_string
        res = applyLFRulesToString(input_string)
        if res == False:
            print 'no match'
        else:
            print 'MATCH: ' + str(res);
        input_string = raw_input('\nInput: ')


def removePunctuationAndLowerTextCasing(text_data):
    text_data = text_data.lower()
    text_data = text_data.replace(',', '')
    text_data = text_data.replace('.', ' ')
    text_data = text_data.replace('!', '')
    text_data = text_data.replace('"', '')
    text_data = text_data.replace('?', '')
    text_data = text_data.replace('*', '')
    text_data = text_data.replace(':', '')
    text_data = text_data.replace('-', ' ')
    text_data = text_data.replace('  ', ' ')
    text_data = text_data.replace('~', '')
    text_data = text_data.replace('\\n', ' ')
    text_data = text_data.replace('=', ' ')     #added 2016/03/01
    return text_data







gl_default_lf_rule_filename = 'tell-phone-number-lf-rules.txt'

#key: first-word-or-category-of-sequence:  value: (rule_lhs, rule_rhs)
#       where rule_lhs is a text representation of a DialogAct, which is Intent(LogicalForm)
#             rule_rhs is a list words or catgories
#
gl_first_word_string_to_rule_dict = {}

#Word-categories are like in Otto, in terms of variables enclosed by brackets [$1]
#e.g. DigitCat[one] <-> one
#This allows a DialogAct rule to be:
#InformTD(ItemValue(Digit($1))) <-> {DigitCat[$1]}
#Where the {DigitCat[$1]} allows 'one' to generate the DialogAct:
#InformTD(ItemValue(Digit(one)))


#key: word-category-predicate              value: list of (wc-lhs, wc-rhs)
#where 
#    wc-lhs is word-category-predicate[arg]
#    wc-rhs is word tuple
# (wc-lhs, wc-rhs) constitutes a word-category rule
#e.g. 
# the Word-Category rules,   
#   'AreaCodeCat[area-code] <-> area code
#   'AreaCodeCat[bozotron-code] <-> bozotron code
# becomes the dictionary entry, 
#    { AreaCodeCat:[(AreaCodeCat[area-code], (area, code)),
#                   (AreaCodeCat[bozotron-code], (bozotron, code)) ]
#
gl_word_category_rules = {}


#Need to make sure that if a DialogAct rhs starts with a word-category, then
#each first word for that word-category adds this DialogRule to the first-word index.


gl_current_rules_filepath = None

def initLFRulesIfNecessary(lf_rule_filename = gl_default_lf_rule_filename):
    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    if gl_current_rules_filepath != filepath:
        initLFRules(lf_rule_filename)


def initLFRules(lf_rule_filename = gl_default_lf_rule_filename):
    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    print 'tellPhoneNumber LF rules filepath: ' + filepath
    gl_current_rules_filepath = filepath
    compileStringToLFRuleDict(filepath)



def compileStringToLFRuleDict(filepath):
    file = open(filepath, "rU")
    
    gl_first_word_string_to_rule_dict = {}
    gl_word_category_rules = {}
    
    rule_text = ''
    word_category_rule_list = []
    dialog_act_rule_list = []
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
                (rule_lhs, rule_rhs) = parseRuleLHSRHS(rule_text)
                lsb_index = rule_lhs.find('[')
                if lsb_index > 0:
                    word_category_rule_list.append((rule_lhs, rule_rhs))
                else:
                    dialog_act_rule_list.append((rule_lhs, rule_rhs))
            rule_text = ''
    file.close()

    for word_category_rule in word_category_rule_list:
        parseAndAddWordCategoryRule(word_category_rule)

    for dialog_act_rule in dialog_act_rule_list:
        parseAndAddDialogActRule(dialog_act_rule)

    sortWordCategoryRulesByLength()        
    print '\nWordCategory rules:'
    printAllWordCategoryRules()
    print '\nDialogAct rules:'
    printAllDialogActRules()



#returns (rule_lhs, rule_rhs)
def parseRuleLHSRHS(rule_text):
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
    return (lhs, rhs)



#A Word-Category rules is a mapping:
#   Predicate[arg] <-> word1 word2...
def parseAndAddWordCategoryRule(str_rule_lhs_rhs):
    lhs = str_rule_lhs_rhs[0]
    rhs = str_rule_lhs_rhs[1]

    rhs = rhs.strip()
    rhs_words = rhs.split()
    rhs_words_tup = tuple(rhs_words)

    lsb_index = lhs.find('[')
    wcategory_predicate = lhs[0:lsb_index]
    this_wcategory_predicate_rule_list = gl_word_category_rules.get(wcategory_predicate)
    if this_wcategory_predicate_rule_list == None:
        this_wcategory_predicate_rule_list = []
        gl_word_category_rules[wcategory_predicate] = this_wcategory_predicate_rule_list
    this_wcategory_predicate_rule_list.append((lhs, rhs_words_tup))


#A DialogAct rule is a mapping:
#   Intent(LogicalForm) <-> word-or-word-category1 word-or-word-category2 ...
#The str_rule_lhs_hrls passed is a tuple (str_lhs, str_rhs)
#This turns the str_rhs into a tuple of either words or word-category predicates.
#This creates a rule, (str_lhs, (word_or_word_category_predicate, word_or_word_category_predicate, ...))
#Then, this picks off the first word_or_word_category_predicate from the rhs tuple.
#If this is a word, then this adds the rule to the gl_first_word_string_to_rule_dict, with the
# key being that word.
#If the first element is a word_category_predicate, then this adds the rule to every first word
#of every arg version for the word_category having that predicate.
def parseAndAddDialogActRule(str_rule_lhs_rhs):
    lhs = str_rule_lhs_rhs[0]
    rhs = str_rule_lhs_rhs[1]

    rhs = rhs.strip()
    #rhs can include word-categories like   {DigitCat[$8]}
    #Make sure these are separated by spaces just in case the rule writer did not include spaces
    #  {DigitCat[$8]}{DigitCat[$9]}
    rhs = rhs.replace('}', '} ')
    rhs = rhs.replace('{', ' {')

    rhs_words = rhs.split()
    rhs_words_tup = tuple(rhs_words)
    first_word_or_cat = rhs_words[0]

    lbr_index = first_word_or_cat.find('{')
    first_words_to_index_under = []

    #If the first word of the word pattern is actually a word category, then we need to 
    #list this DialogRule under each first word of each arg version of that category 
    #  {predicate[$a]}
    if lbr_index >= 0:
        lsq_index = first_word_or_cat.find('[')
        predicate = first_word_or_cat[lbr_index+1:lsq_index]
        cat_list = gl_word_category_rules.get(predicate)
        if cat_list == None:
            print 'Problem in parseAndAddDialogActRule. Predicate ' + predicate + ' not found in word-cateogry dict'
            return
        #print 'cat_list: ' + str(cat_list)
        for cat_rule in cat_list:
            #print 'cat_rule: ' + str(cat_rule)
            rhs = cat_rule[1]
            first_word = rhs[0]
            #print 'first_word: ' + str(first_word)
            first_words_to_index_under.append(first_word)
    else:
        first_words_to_index_under.append(first_word_or_cat)

    #print 'first_words_to_index_under: ' + str(first_words_to_index_under)

    for first_word_to_index_under in first_words_to_index_under:
        first_word_rule_list = gl_first_word_string_to_rule_dict.get(first_word_to_index_under)
        if first_word_rule_list == None:
            first_word_rule_list = []
            gl_first_word_string_to_rule_dict[first_word_to_index_under] = first_word_rule_list
        first_word_rule_list.append((lhs, rhs_words_tup))




#gl_word_category_rules is a dictionary:
#   key: word-category-predicate   value: list of word-category rules with this predicate
#Different word-category rules share the same predicate but have different arg and 
#possibly different numbers of words in their text utterance.
#This runs through all of the word-category predicates in gl_word_category_rules, and
#for each one, it sorts its list of word-category rules from longest to shortest.
def sortWordCategoryRulesByLength():
    for predicate in gl_word_category_rules.keys():
        rule_list = gl_word_category_rules.get(predicate)
        rule_list.sort(key = lambda wc_rule_tup: len(wc_rule_tup[1]))  # sorts in place, key is len of rhs of the rule
        rule_list.reverse()


def printAllWordCategoryRules():
    for predicate in gl_word_category_rules.keys():
        print 'predicate: ' + predicate
        rule_list = gl_word_category_rules.get(predicate)
        for rule in rule_list:
            print '    '  + str(rule)


def printAllDialogActRules():
    for rule_key in gl_first_word_string_to_rule_dict.keys():
        print rule_key
        rule_list = gl_first_word_string_to_rule_dict[rule_key]
        for rule in rule_list:
            print '    '  + str(rule)



#Assumes the rule set has already been loaded by initLFRulesIfNecessary() or a related function.
def applyLFRulesToString(input_string):
    word_list = input_string.split()
    i_word = 0;
    
    fit_rule_list = []    #a list of rule fits to the_string: [(DialogAct, start_i, end_i),...]
    while i_word < len(word_list):
        word_i = word_list[i_word]
        possible_rules = gl_first_word_string_to_rule_dict.get(word_i)
        print '\'' + word_i + '\':   possible_rules: ' + str(possible_rules)
        if possible_rules != None:
            for possible_rule in possible_rules:
                print 'possible_rule: ' + str(possible_rule)
                #fit_tuple is (dialog_rule, i_word_start, i_word_end)  
                fit_tuple = testRuleOnInputWordsAtWordIndex(possible_rule, word_list, i_word)
                if fit_tuple != None:
                    fit_rule_list.append(fit_tuple)
                    print 'fit_tuple: ' + str(fit_tuple)
        i_word += 1
    
    print 'found ' + str(len(fit_rule_list)) + ' matches'
    res = selectMaximallyCoveringRules(fit_rule_list, len(word_list))
    print 'narrowed down to ' + str(len(res)) + ' matches'
    return res



#fit_rule_list is a list of tuples: (DialogAct, start_index, stop_index)
#where start_index and stop_index are indices into a word list for input text 
#Some of the tuples could overlap and claim the same words.
#This function selects the longest (most-word) fitting tuples in a greedy fashion
#Returns a list of tuples which is a subset of the tuples passed
def selectMaximallyCoveringRules(fit_rule_list, input_length):
    covered_word_flag_ar = [False] * input_length;
    res = []
    fit_rule_list.sort(key = lambda tup: tup[2]-tup[1])
    fit_rule_list.reverse()
    for fit_rule_tup in fit_rule_list:
        ok_p = True
        for ii in range(fit_rule_tup[1], fit_rule_tup[2]+1):
            if covered_word_flag_ar[ii] == True:
                ok_p = False
                break
        if ok_p == True:
            res.append(fit_rule_tup)
            for ii in range(fit_rule_tup[1], fit_rule_tup[2]+1):
                covered_word_flag_ar[ii] = True
    res.sort(key = lambda tup: tup[1])
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

    print ' testRuleOnInputWordsAtWordIndex(' + str(rule) + ', ' + str(word_list) + ', ' + str(i_word_start) + ')'
    rule_rhs_items = rule[1]
    arg_index_map = {}    #key: $X where X is an argument indicator, value:  a predicate provided by a word-category
                          #that will substitute for $X in the DialogAct returned (if it matches)
    i_word = i_word_start
    i_rule = 0
    #    rule_rhs_items = rule_rhs.split()
    print ' rule_rhs_items: ' + str(rule_rhs_items)
    #    while i_word < len(word_list):
    while True:   #march along until either the end of the dialog rule word list or the input word list is exhausted, 
                  #This test is below.
        rule_word_or_word_category = rule_rhs_items[i_rule]
        print '  test: ' + str(i_word) + ': ' + rule_word_or_word_category

        #rule_word_or_word_category is either a word or else an indicator of a word-category, like, {DigitCat[$1]}
        if rule_word_or_word_category.find('{') == 0:
            lbr_index = rule_word_or_word_category.find('[')
            word_category_predicate = rule_word_or_word_category[1:lbr_index]
            word_category = gl_word_category_rules.get(word_category_predicate)
            if word_category == None:
                print 'testRuleOnInputWordsAtWordIndex() could not find word-category ' + word_category_predicate
                i_word += 1
                continue
            (num_words_consumed, word_category_arg) = testWordCategoryOnInputWordsAtWordIndex(word_category_predicate, 
                                                                                              word_list, i_word)
            print 'testWordCategory... consumed ' + str(num_words_consumed) + ' words'
            if num_words_consumed > 0:
                lsb_index = rule_word_or_word_category.find('[$')
                rsb_index = rule_word_or_word_category.find(']')
                arg_name = rule_word_or_word_category[lsb_index+2:rsb_index]
                arg_index_map[arg_name] = word_category_arg
                i_word += num_words_consumed
                i_rule += 1
            else:
                #if we're looking for a word category, allow intervening words
                i_word += 1
        else:
            #if a word-to-word match, then advance
            if word_list[i_word] == rule_word_or_word_category:
                i_word += 1
                i_rule += 1
            #if a word-to-word non-match, then this rule doesn't apply
            else:
                print 'word-to-word non-match ' + word_list[i_word] + ' : ' + rule_word_or_word_category
                return None


        #the DialogAct matches
        if i_rule >= len(rule_rhs_items):
            print '\n****DialgAct matches: i_word: ' + str(i_word) + ' i_rule: ' + str(i_rule)
            break

        if i_word > len(word_list):
            print 'ran out of words'
            return None

    rule_dialog_act = rule[0]
    print 'matched all words did DialogRule ' + rule_dialog_act
    print 'arg_index_map: ' + str(arg_index_map)
    d_index = rule_dialog_act.find('$')
    print ' d_index: ' + str(d_index)
    while d_index > 0:
        #need to parse out forms:  ($1); ($1, $2, $3)
        comma_index = rule_dialog_act.find(',', d_index+1)
        rp_index = rule_dialog_act.find(')', d_index+1)
        if comma_index > 0 and comma_index > d_index+1 and comma_index < rp_index:
            rp_index = comma_index
        print ' rp_index: ' + str(rp_index)
        if rp_index < d_index:
            print 'testRuleOnInputWordsAtWordIndex() found a minsmatched braces in a rule DialogAct: ' + rule_dialog_act
            return None
        da_arg_name = rule_dialog_act[d_index+1:rp_index]
        print ' da_arg_name: ' + da_arg_name
        word_category_arg = arg_index_map.get(da_arg_name)
        if word_category_arg != None:
            rule_dialog_act = rule_dialog_act[0:d_index] + word_category_arg + rule_dialog_act[rp_index:]
        d_index = rule_dialog_act.find('$', rp_index+1)
    print 'returning ' + str((rule_dialog_act, i_word_start, i_word)) + '\n'
    return (rule_dialog_act, i_word_start, i_word-1)




#Tests all arg versions of the word_category for the word_category_predicate passed on the 
#word_list starting at i_word
#If there's a word-by-word match for all words in the word tuple of a word-category, then
#that arg is returned along with that word_category's length (number of words)
#Preferably, the list of word_categories in gl_word_category_rules would have been sorted by 
#length so that the longest possible match is returned
#returns (num_words_consumed, word_category_arg)
def testWordCategoryOnInputWordsAtWordIndex(word_category_predicate, word_list, i_word_start):
    
    if i_word_start >= len(word_list):
        return (0, None)

    word_category_rules = gl_word_category_rules.get(word_category_predicate)

    print 'testWordCategoryOnInputWordsAtWordIndex(' + word_category_predicate + ', ' + str(word_list) + ', ' + str(i_word_start) + ')'

    wc_rule_list = gl_word_category_rules.get(word_category_predicate)
    if wc_rule_list == None:
        print 'problem in testWordCategoryOnInputWordsAtWordIndex() no wc rules for predicate ' + word_category_predicate
        return (0, None)

    for wc_rule in wc_rule_list:
        rhs = wc_rule[1]  #a tuple of words 

        i_word = i_word_start
        i_wc_word = 0
        match_p = True
        while i_wc_word < len(rhs) and i_word < len(word_list):
            word_i = word_list[i_word]
            wc_word = rhs[i_wc_word]
            if word_i != wc_word:
                match_p = False
                break
            i_word += 1
            i_wc_word += 1
        if match_p:
            lhs = wc_rule[0]
            lsb_index = lhs.find('[')
            rsb_index = lhs.find(']')
            wc_arg = lhs[lsb_index+1:rsb_index]
            return ( len(rhs), wc_arg)

    return (0, None)






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



        
        

                        



###############################################################################
#
#archives
#

#Determines if the rule as written out in rule_text is a Word-Category rule or a DialogAct rule
#A Word-Category rules is a mapping:
#   Predicate[arg] <-> word1 word2...
#A DialogAct rule is a mapping:
#   Intent(LogicalForm) <-> word-or-word-category1 word-or-word-category2 ...
def parseAndAddRuleObsolete(rule_text):
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

    #determine if a DialogRule or else a Word Category
    lsb_index = lhs.find('[')
    if lsb_index > 0:               #Word Category
        wcategory_predicate = lhs[0:lsb_index]
        word_list = rhs.split()
        word_tuple = tuple(word_list)
        this_wcategory_predicate_rule_list = gl_word_category_rules.get(wcategory_predicate)
        if this_wcategory_predicate_rule_list == None:
            this_wcategory_predicate_rule_list = []
        this_wcategory_predicate_rule_list.append((lhs, word_tuple))

    else:                           #DialogRule
        existing_list = gl_first_word_string_to_rule_dict.get(first_string_or_category)
        if existing_list == None:
            new_rule_list = [rule]
            gl_first_word_string_to_rule_dict[first_string_or_category] = new_rule_list
        else:
            existing_list.append(rule)
