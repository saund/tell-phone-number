#!/usr/bin/python -tt

#ruleProcessing.py is for reading in Otto-like rules, and using the rules 
#to process input text to produce DialogActs.
#
#A DialogAct is of the form,     Predicate(LogicalForm, LogicalForm, ...)
#
#A LogicalForm is of the form,   Predicate(LogicalForm, LogicalForm, ...)
#or                              Predicate
#
#Thus two DialogAct might be:    RequestTopicInfo(receive-telephone-number)
#                                InformTD(IndexicalPosition(first))
#
#In this module, the DialogAct results of processing are expressed only as strings.
#It is up to the calling module to parse a string DialogAct into 
#Intents, LogicalForms, and the predicates and arguments that comprise LogicalForms.


import csv
import random
import sys
import copy
import re
import os
import math


gl_tell = False

def setTell(val):
    gl_tell = val



####################
#
#Test loop
#


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




#
#
####################

####################
#
#Loading rules from the rules file
#


gl_default_lf_rule_filename = 'tell-phone-number-lf-rules.txt'

#key: first-word-or-category-of-sequence:  value: (rule_lhs, rule_rhs)
#       where rule_lhs is a text representation of a DialogAct, which is Intent(LogicalForm)
#             rule_rhs is a list words or catgories
#
gl_first_word_string_to_rule_dict = {}


#key: intent predicate of the DialogAct
#value: a list of tuples for this intent: [(da, rhs), (da, rhs)...]
#where da is a DialogAct instance
#      rhs is a string of a list of words or category objects e.g. {PredCat[$1]}
gl_dialog_act_rules = {}

#Word-categories are like in Otto, in terms of variables enclosed by brackets [$1]
#e.g. DigitCat[one] <-> one
#This allows a DialogAct rule to be:
#InformTD(ItemValue(Digit($1))) <-> {DigitCat[$1]}
#Where the {DigitCat[$1]} allows 'one' to generate the DialogAct:
#InformTD(ItemValue(Digit(one)))
#
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




gl_current_rules_filepath = None

def initLFRulesIfNecessary(lf_rule_filename = gl_default_lf_rule_filename):
    global gl_current_rules_filepath
    global gl_rules_dirpath
    
    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    if gl_current_rules_filepath != filepath:
        initLFRules(lf_rule_filename)


def initLFRules(lf_rule_filename = gl_default_lf_rule_filename):
    global gl_current_rules_filepath
    global gl_rules_dirpath

    filepath = gl_rules_dirpath + '/' + lf_rule_filename
    print 'tellPhoneNumber LF rules filepath: ' + filepath
    gl_current_rules_filepath = filepath
    compileStringToLFRuleDict(filepath)



def compileStringToLFRuleDict(filepath):
    file = open(filepath, "rU")
    global gl_first_word_string_to_rule_dict
    global gl_dialog_act_rules
    global gl_word_category_rules
    
    gl_first_word_string_to_rule_dict = {}
    gl_dialog_act_rules = {}
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
    global gl_word_category_rules
    global gl_first_word_string_to_rule_dict

    lhs = str_rule_lhs_rhs[0]
    rhs = str_rule_lhs_rhs[1]
    rhs = rhs.strip()
    #rhs can include word-categories like   {DigitCat[$8]}
    #Make sure these are separated by spaces just in case the rule writer did not include spaces
    #  {DigitCat[$8]}{DigitCat[$9]}
    rhs = rhs.replace('}', '} ')
    rhs = rhs.replace('{', ' {')

    da = parseDialogActFromString(lhs)
    da_list = gl_dialog_act_rules.get(da.intent)
    if da_list == None:
        da_list = []
        gl_dialog_act_rules[da.intent] = da_list
    da_list.append((da, rhs))

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
            if not first_word in first_words_to_index_under:
                first_words_to_index_under.append(first_word)
    else:
        if not first_word_or_cat in first_words_to_index_under:
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
    global gl_word_category_rules

    for predicate in gl_word_category_rules.keys():
        rule_list = gl_word_category_rules.get(predicate)
        rule_list.sort(key = lambda wc_rule_tup: len(wc_rule_tup[1]))  # sorts in place, key is len of rhs of the rule
        rule_list.reverse()


def printAllWordCategoryRules():
    global gl_word_category_rules

    for predicate in gl_word_category_rules.keys():
        print 'predicate: ' + predicate
        rule_list = gl_word_category_rules.get(predicate)
        for rule in rule_list:
            print '    '  + str(rule)


def printAllDialogActRules():
    global gl_first_word_string_to_rule_dict

    for rule_key in gl_first_word_string_to_rule_dict.keys():
        print rule_key
        rule_list = gl_first_word_string_to_rule_dict[rule_key]
        for rule in rule_list:
            print '    '  + str(rule)



#
#
####################

####################
#
#DialogAct and LogicalForm classes, and 
#functions for parsing a LHS into a DialogAct instance
#


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
    def __init__(self, predicate):
        self.predicate = predicate   #If there are args, then this will be uppercase.  If this is an itself just an argument,
                                     #then this is likely to be lowercase.
        self.arg_list = []

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        print_string = self.predicate + ''
        if len(self.arg_list) > 0:
            print_string += '('
            argsep = ''
            for arg in self.arg_list:
                arg_str = arg.getPrintString()
                print_string += argsep 
                print_string += arg_str
                argsep = ','
            print_string += ')'
        return print_string


class DialogAct(LogicalForm):
    def __init__(self, intent):
        self.intent = intent
        self.arg_list = []

    def printSelf(self):
        print self.getPrintString()

    def getPrintString(self):
        print_string = self.intent + ''
        if len(self.arg_list) > 0:
            print_string += '('
            argsep = ''
            for arg in self.arg_list:
                arg_str = arg.getPrintString()
                print_string += argsep 
                print_string += arg_str
                argsep = ','
            print_string += ')'
        return print_string



#rule_match_list is a list of tuples, (str_dialog_act, start_index, end_index)
#Returns a list of DialogActs
def parseDialogActsFromRuleMatches(rule_match_list):
    da_list = []
    for match_tuple in rule_match_list:
        str_dialog_act = match_tuple[0]
        da = parseDialogActFromString(str_dialog_act)
        da_list.append(da)

    return da_list
    
    

#str_dialog_act is of the form, 
#   Predicate(LogicalForm, LogicalForm, ...)
#
def parseDialogActFromString(str_dialog_act):
    #print 'parseDialogActFromString(  ' + str_dialog_act + '  )'
    lp_index = str_dialog_act.find('(')
    intent = str_dialog_act[0:lp_index]
    #print 'lp_index: ' + str(lp_index) + '  intent: ' + intent
    da = DialogAct(intent)
    arg_str = str_dialog_act[lp_index+1:len(str_dialog_act)-1]
    #print 'arg_str: ' + arg_str
    str_arg_list = parsePredicatesWithArgs(arg_str)
    #print 'str_arg_list: ' + str(str_arg_list)

    lf_arg_list = []
    #print 'lf_arg_list: ' + str(lf_arg_list)
    for str_arg in str_arg_list:
        #print 'str_arg: ' + str_arg
        lf_arg = parseLogicalFormFromString(str_arg)
        lf_arg_list.append(lf_arg)
    da.arg_list = lf_arg_list
    return da


def parseLogicalFormFromString(str_lf):
    #print 'parseLogicalFormFromString(  ' + str_lf + '  )'
    lp_index = str_lf.find('(')
    if lp_index < 0:
        lf = LogicalForm(str_lf)
        #print 'found primitive lf: ' + lf.getPrintString()
        return lf
    predicate = str_lf[0:lp_index]
    lf = LogicalForm(predicate)
    arg_str = str_lf[lp_index+1:len(str_lf)-1]
    str_arg_list = parsePredicatesWithArgs(arg_str)
    #print 'str_arg_list: ' + str(str_arg_list)
    lf_arg_list = []
    for str_arg in str_arg_list:
        #print '   str_arg: ' + str_arg
        lf_arg = parseLogicalFormFromString(str_arg)
        lf_arg_list.append(lf_arg)
    lf.arg_list = lf_arg_list
    return lf



#str_preds_args is a string of the form, 
#  lf1, lf2, lf3...
# where each lf is a LogicalForm that could be nested,  pred(lf, lf, lf) 
#This returns a list, [lf1, lf2, lf3...]
# e.g.
#  'pred1(pred1a(pred1aa(pred1aaa, pred1aab), pred1ab(pred1aba, pred1abb)), pred1b), pred2(pred2a(pred2aa, pred2ab))'
#  returns [  'pred1(pred1a(pred1aa(pred1aaa, pred1aab), pred1ab(pred1aba, pred1abb)), pred1b)', 
#             'pred2(pred2a(pred2aa, pred2ab))' ]
def parsePredicatesWithArgs(str_preds_args):
    
    last_idx = 0
    lp_idx = str_preds_args.find('(', last_idx)
    comma_idx = str_preds_args.find(',', last_idx)
    str_arg_list = []
    
    #print 'parsePredicatesWithArgs( ' + str_preds_args + ' )'
    #print ' lp_idx: ' + str(lp_idx) + ' comma_idx: ' + str(comma_idx)

    while lp_idx > 0 or comma_idx > 0:
        #comma demarks the next arg
        if lp_idx < 0 or (comma_idx >0 and comma_idx < lp_idx):
            key_idx = comma_idx
            arg = str_preds_args[last_idx:key_idx]
            str_arg_list.append(arg)
            last_idx = key_idx+1
            lp_idx = str_preds_args.find('(', last_idx)
            comma_idx = str_preds_args.find(',', last_idx)
        #next arg is a predicate with parens
        elif comma_idx < 0 or (lp_idx > 0 and lp_idx < comma_idx):
            key_idx = lp_idx
            paren_count = 1
            
            while paren_count > 0:
                key_idx += 1
                if key_idx >= len(str_preds_args):
                    print 'error parsePredicatesWithArgs found unbalanced parentheses ' + str_preds_args
                    return []
                if str_preds_args[key_idx] == '(':
                    paren_count += 1
                if str_preds_args[key_idx] == ')':
                    paren_count -= 1

            arg = str_preds_args[last_idx:key_idx+1]  #include the ')'
            #print 'appending ' + arg
            str_arg_list.append(arg)
            key_idx += 1
            if key_idx >= len(str_preds_args):
                return str_arg_list
                last_idx = key_idx+1
                lp_idx = str_preds_args.find('(', last_idx)
                comma_idx = str_preds_args.find(',', last_idx)

    if last_idx < len(str_preds_args):
        arg = str_preds_args[last_idx:]
        str_arg_list.append(arg)
    return str_arg_list



#
#
####################


####################
#
#Interpretion of text input using rules
#        
#This works in terms only of gl_first_word_string_to_rule_dict 
#which uses a tuple (lhs, rhs) version of the rules, where lhs and rhs are strings.
#This does not use the DialogAct or LogicalForm classes.
#That would be an alternative way of doing it but it doesn't seem necessary.
#

#Assumes the rule set has already been loaded by initLFRulesIfNecessary() or a related function.
def applyLFRulesToString(input_string):
    global gl_first_word_string_to_rule_dict

    word_list = input_string.split()
    i_word = 0;
    
    fit_rule_list = []    #a list of rule fits to the_string: [(DialogAct, start_i, end_i),...]
    while i_word < len(word_list):
        word_i = word_list[i_word]
        possible_rules = gl_first_word_string_to_rule_dict.get(word_i)
        #print '\'' + word_i + '\':   possible_rules: ' + str(possible_rules)
        if possible_rules != None:
            for possible_rule in possible_rules:
                #print 'possible_rule: ' + str(possible_rule)
                #fit_tuple is (dialog_rule, i_word_start, i_word_end)  
                fit_tuple = testRuleOnInputWordsAtWordIndex(possible_rule, word_list, i_word)
                if fit_tuple != None:
                    fit_rule_list.append(fit_tuple)
                    #print 'fit_tuple: ' + str(fit_tuple)
        i_word += 1
    
    if gl_tell:
        print 'found ' + str(len(fit_rule_list)) + ' matches'
    res = selectMaximallyCoveringRules(fit_rule_list, len(word_list))
    if gl_tell:
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
    global gl_word_category_rules

    #print ' testRuleOnInputWordsAtWordIndex(' + str(rule) + ', ' + str(word_list) + ', ' + str(i_word_start) + ')'
    rule_rhs_items = rule[1]
    arg_index_map = {}    #key: $X where X is an argument indicator, value:  a predicate provided by a word-category
                          #that will substitute for $X in the DialogAct returned (if it matches)
    i_word = i_word_start
    i_rule = 0
    #print ' rule_rhs_items: ' + str(rule_rhs_items)
    while True:   #march along until either the end of the dialog rule word list or the input word list is exhausted, 
                  #This test is below.
        rule_word_or_word_category = rule_rhs_items[i_rule]
        #print '  test: ' + str(i_word) + ': ' + rule_word_or_word_category

        #rule_word_or_word_category is either a word or else an indicator of a word-category, like, {DigitCat[$1]}
        if rule_word_or_word_category.find('{') == 0:
            lbr_index = rule_word_or_word_category.find('[')
            word_category_predicate = rule_word_or_word_category[1:lbr_index]
            word_category = gl_word_category_rules.get(word_category_predicate)
            if word_category == None:
                print 'error testRuleOnInputWordsAtWordIndex() could not find word-category ' + word_category_predicate
                i_word += 1
                continue
            (num_words_consumed, word_category_arg) = testWordCategoryOnInputWordsAtWordIndex(word_category_predicate, 
                                                                                              word_list, i_word)
            #print 'testWordCategory can consume ' + str(num_words_consumed) + ' words'
            #The word_category_arg tell which arg version of the Word-Category matched
            #If the rule_word_or_word_category has a settable argument $arg_name,  then stuff a map.
            #If the rule_word_or_word_category has a specified argument, then only accept the match if it matches
            # word_category_arg
            if num_words_consumed > 0:
                lsb_index = rule_word_or_word_category.find('[')

                #No args case, just a predicate
                if lsb_index < 0:
                    i_word += num_words_consumed
                    i_rule += 1
                elif rule_word_or_word_category[lsb_index+1] == '$':
                    rsb_index = rule_word_or_word_category.find(']')
                    arg_name = rule_word_or_word_category[lsb_index+2:rsb_index]
                    arg_index_map[arg_name] = word_category_arg
                    i_word += num_words_consumed
                    i_rule += 1
                else:
                    rsb_index = rule_word_or_word_category.find(']')
                    arg_name = rule_word_or_word_category[lsb_index+1:rsb_index]
                    if word_category_arg == arg_name:
                        i_word += num_words_consumed
                        i_rule += 1
                    else:
                        #print 'matched arg ' + word_category_arg + ' does not match required arg ' + arg_name
                        return None                        
            else:
                #if we're looking for a word category, allow intervening words
                i_word += 1
        else:
            if i_word >= len(word_list):
                #print 'ran out of words A'
                return None
            #if a word-to-word match, then advance
            #print 'word_list[' + str(i_word) + ']:' + word_list[i_word]  + ' rule_word_or_word_cat: ' + str(rule_word_or_word_category)
            if word_list[i_word] == rule_word_or_word_category:
                i_word += 1
                i_rule += 1
            #if a word-to-word non-match, then this rule doesn't apply
            else:
                #print 'word-to-word non-match ' + word_list[i_word] + ' : ' + rule_word_or_word_category
                return None


        #the DialogAct matches
        if i_rule >= len(rule_rhs_items):
            #print '\n****DialgAct matches: i_word: ' + str(i_word) + ' i_rule: ' + str(i_rule)
            break

        if i_word > len(word_list):  # >= or > ?
            #print 'ran out of words B'
            return None

    rule_dialog_act = rule[0]
    d_index = rule_dialog_act.find('$')
    while d_index > 0:
        #need to parse out forms:  ($1); ($1, $2, $3)
        comma_index = rule_dialog_act.find(',', d_index+1)
        rp_index = rule_dialog_act.find(')', d_index+1)
        if comma_index > 0 and comma_index > d_index+1 and comma_index < rp_index:
            rp_index = comma_index
        if rp_index < d_index:
            print 'error testRuleOnInputWordsAtWordIndex() found a minsmatched braces in a rule DialogAct: ' + rule_dialog_act
            return None
        da_arg_name = rule_dialog_act[d_index+1:rp_index]
        word_category_arg = arg_index_map.get(da_arg_name)
        if word_category_arg != None:
            rule_dialog_act = rule_dialog_act[0:d_index] + word_category_arg + rule_dialog_act[rp_index:]
        d_index = rule_dialog_act.find('$', rp_index+1)
    #print 'returning ' + str((rule_dialog_act, i_word_start, i_word)) + '\n'
    return (rule_dialog_act, i_word_start, i_word-1)




#Tests all arg versions of the word_category for the word_category_predicate passed on the 
#word_list starting at i_word
#If there's a word-by-word match for all words in the word tuple of a word-category, then
#that arg is returned along with that word_category's length (number of words)
#Preferably, the list of word_categories in gl_word_category_rules would have been sorted by 
#length so that the longest possible match is returned
#returns (num_words_consumed, word_category_arg)
def testWordCategoryOnInputWordsAtWordIndex(word_category_predicate, word_list, i_word_start):
    global gl_word_category_rules
    
    if i_word_start >= len(word_list):
        return (0, None)

    word_category_rules = gl_word_category_rules.get(word_category_predicate)

    #print 'testWordCategoryOnInputWordsAtWordIndex(' + word_category_predicate + ', ' + str(word_list) + ', ' + str(i_word_start) + ')'

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
            #print 'testWordCategory...' + word_category_predicate + ' returning (' + str(len(rhs)) + ', ' + wc_arg + ')'
            return ( len(rhs), wc_arg)

    return (0, None)


#
#
####################

####################
#
#Generator rules
#

def generateTextFromDialogActs(da_list):
    text_list = []
    for da in da_list:
        text_utterance = generateTextFromDialogAct(da)
        if text_utterance == None:
            print 'error could not generate text from DialogAct ' + da.getPrintString()
        else:
            text_list.append(text_utterance)
    return text_list



#dialog_act is an instance of a DialogAct
#Where each LogicalForm is itself a predicate or predicate(lf1, lf2...)
#The most interesting thing this function does is fill in the free arguments $1, $2 etc.
#from the DialogRule to the utterance.
def generateTextFromDialogAct(gen_dialog_act):
    da_rule_list = gl_dialog_act_rules.get(gen_dialog_act.intent)
    if da_rule_list == None:
        print 'error generateTextFromDialogAct() sees no rules for dialog_act ' + gen_dialog_act.getPrintString() + ' intent ' + gen_dialog_act.intent
        return None
    
    #Run through all of the LogicalForms and Word-Category rules that use this intent in its DialogAct.
    #Match predicte-by-predicate recursively.  As free arguments are encountered in the rule, map them
    #to argument values from the arguments of the generated LogicalForm.
    #Return the argument mapping for the first match to the dialog_act passed.
    arg_mapping = None
    for da_rule in da_rule_list:
        rule_da = da_rule[0]
        arg_mapping = recursivelyMapDialogRule(rule_da, gen_dialog_act)
        if arg_mapping != None:
            break
    if arg_mapping == None:
        print 'error generateTextFromDialogAct() could not find a consistent recursive mapping for dialog_act\n '\
            + gen_dialog_act.getPrintString() + ' intent ' + gen_dialog_act.intent
        return None

    word_list = []
    rhs = da_rule[1]
    rhs_list = rhs.split()
    print 'rhs: ' + str(rhs)
    for word_or_word_category in rhs_list:
        if word_or_word_category[0] == '{':
            lsb_index = word_or_word_category.find('[')
            rsb_index = word_or_word_category.find(']', lsb_index)
            print 'word_or_word_category: ' + str(word_or_word_category)
            wc_predicate = word_or_word_category[:lsb_index]
            arg_name = word_or_word_category[lsb_index+2:rsb_index]
            arg_value = arg_mapping.get(arg_name);
            if arg_value == None:
                print 'error arg_name ' + arg_name + ' not found in mapping ' + str(arg_mapping)
            else:
                #$$XX here need to mix in the other words of the word-category
                word_list.append(arg_value)
        else:
            word_list.append(word_or_word_category)

    out_string = ' '.join(word_list)
    return out_string



#recursively checks all predicates and argugments of the template rule_da against the 
#generated DialogAct gen_da.  
#Fills in an argument map as it goes, leaving off the dollar signs.
#If successful match, then returns the argument_map.
#If something doesn't match, then this returns None.
def recursivelyMapDialogRule(rule_da, gen_da):
    print '\nrule_da: ' + rule_da.getPrintString()
    print 'gen_da: ' + gen_da.getPrintString()
    arg_mapping = {}
    ok_p = recursivelyMapDialogRuleAux(rule_da, gen_da, arg_mapping)
    if ok_p:
        return arg_mapping
    else:
        return None
    
def recursivelyMapDialogRuleAux(rule_da, gen_da, arg_mapping):
    print '\nrecurse'
    print 'rule_da: ' + rule_da.getPrintString()
    print 'gen_da: ' + gen_da.getPrintString()

    if type(rule_da) != type(gen_da):
        print 'type(rule_da) ' + str(type(rule_da)) + ' != type(gen_da) ' + str(type(gen_da))
        return False
    if len(rule_da.arg_list) != len(gen_da.arg_list):
        print 'len(rule_da.arg_list) ' + str(len(rule_da.arg_list)) + ' != len(gen_da.arg_list) ' + str(len(gen_da.arg_list))
        return False


    if len(rule_da.arg_list) == 0:
        d_index = rule_da.predicate.find('$')
        if d_index == 0:
            arg_name = rule_da.predicate[1:]
            arg_value = gen_da.predicate
            print 'adding arg_mapping[' + arg_name + '] = ' + arg_value
            arg_mapping[arg_name] = arg_value
            return True
        else:
            if rule_da.predicate == gen_da.predicate:
                return True
            else:
                print 'rule_da.predicate ' + rule_da.predicate + ' != gen_da.predicate ' + gen_da.predicate
                return False
    else:
        for i in range(0, len(rule_da.arg_list)):
            rule_da_arg = rule_da.arg_list[i]
            gen_da_arg = gen_da.arg_list[i]
            if type(rule_da_arg) != type(gen_da_arg):
                print 'arg ' + str(i) + ': type(rule_da_arg) ' + str(type(rule_da_arg)) + ' != type(gen_da_arg) ' + str(type(gen_da_arg))
                return False
            elif type(rule_da_arg) != str:
                print 'rule_da_arg: ' + str(rule_da_arg) + ' type(rule_da_arg): ' + str(type(rule_da_arg))
                vv =  recursivelyMapDialogRuleAux(rule_da_arg, gen_da_arg, arg_mapping)
                if vv == False:
                    return False
        return True






#
#
####################

