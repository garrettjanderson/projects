import numpy as np
import pandas as pd
import re
from nltk import WordNetLemmatizer, sent_tokenize, word_tokenize
import gensim
import multiprocessing
cores = multiprocessing.cpu_count()

import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)


def get_book_text(filename):
    '''
    Input: Filename of target text file
    Output: text file as a single string
    '''
    with open(filename,encoding = 'windows-1252') as f:
        text = f.read()
    return text



def clean_artifacts(text):
    '''
    Cleans OCR artifacts out of text

    Input: Text string (output of get_book_text)
    Output: Cleaned text string
    '''
    #Remove page/chapter numbers, and any number erroneously created by OCR
    text = re.sub(r'[1234567890]+','',text)

    #Remove line breaks, apostrophes (important for finding quotes), and replace 'l(' with k (OCR artifact)
    text = text.replace('\n', ' ')
    text = text.replace("\'",'')
    text = text.replace("l(",'k')
    #Remove the word 'page' from every instance of 'Page ##'
    text = text.replace('Page ','')
    #Eddard stark is sometime referred to as Eddard, sometimes as Ned. Let's fix that.
    text = text.replace('Ned','Eddard')
    #The same is true for Petyr Baelish and 'Littlefinger'
    text = text.replace('Littlefinger','Petyr')
    #And Dany/Daenerys
    text = text.replace('Dany','Daenerys')
    #...Joffrey too
    text = text.replace('loff','Joff')
    text = text.replace('Joffrey','Joff')
    text = text.replace('Joff', 'Joffrey')
    text = text.replace('Brorm','Bronn')

    #Samwell<-> Sam
    text = re.sub(r'Sam[ ,.?]','Samwell',text)

    #Brynden "Blackfish" Tully
    text = text.replace('Blackfish', 'Brynden')

    #The brothers Clegane
    text = text.replace('The Hound', 'Sandor')
    text = text.replace('The Mountain', 'Gregor')

    #Leverage all caps words to increase padding between chapters
    for n in ['EDDARD','CATELYN','SANSA','ARYA','BRAN','JON','DAENERYS','TYRION','THEON','DAVOS','SAMWELL','JAIME','CERSEI','BRIENNE','AREO','ARYS','ARIANNE','ASHA','AERON','VICTARION','QUENTYN','JON','BARRISTAN','MELISANDRE']:
        text = text.replace(n, 'This is a filler string intended to act as a buffer between chapters to help prevent characters from leaking over into the previous chapter thereby really messing up the distance metrics.')

    return text



def break_sentences(text):
    '''
    Uses nltk sentence tokenizer to split text into a list of individual sentences
    Input: Text (string)
    Output: text_sent (list of strings)
    '''
    #Sentence tokenization
    text_sent = sent_tokenize(text)

    #If a single spoken line has more than one sentence in it, include the quotes in all pieces of the sentence
    for i in range(len(text_sent)):
        if text_sent[i].count('"') == 1:
            if text_sent[i].startswith('"'):
                text_sent[i] = text_sent[i]+'"'
            elif text_sent[i].endswith('"'):
                text_sent[i] = '"'+text_sent[i]
    return text_sent



def find_quote_ind(text_sent):
    '''
    Finds indices and quotes for text lines containing dialogue
    Input: Sentence tokenized text
    Output: all_quote_indices (list of lists of ints, each sublist containing a distinct dialogue chunk)
    '''
    #Enumerate sentences and keep only those with quotation marks in them
    text_enum = enumerate(text_sent)
    text_chunks = [idx for idx, sent in text_enum if '"' in sent]

    #Group all dialogue sentences based on continuity of numerical indices
    indices = []
    from itertools import groupby
    from operator import itemgetter
    data = text_chunks.copy()
    for idx, sent in groupby(enumerate(text_chunks), lambda ix: ix[0]-ix[1]):
        indices.append(list(map(itemgetter(1), sent)))
    return indices



def group_quotes(sents, quote_ind):
    '''
    Creates documents containing distinct sections of dialogue from the input sents and quote chunk indices
    Input:
          sents - list of strings, each a sentence from the original text that contains a quotation mark
          quote_ind - List of lists, each sublist containing the indices of a distinct dialogue chunk (ouput of find_quote_ind)
    Output:
          first_quote_ind - list of the first index number for each item in quote_ind (Used to tie quotes back to )
          grouped_quotes - List of strings, each a distinct conversation from the original text
    '''
    grouped_quotes = []
    for elem in quote_ind:
        q = []
        for ind in elem:
            q.append(sents[ind])
        grouped_quotes.append(''.join(q))
    return grouped_quotes



def replace_quote_with_idx(enum_sents):
    '''
    Replaces the text in the original book with the index where it appears
    Input: List of tuples like (int, string) representing (sentence index, quoted text)
    Output: enum_sents, with strings replaced with the index where the quote appears
    '''
    regex = re.compile(r'["\'].*["\']')
    quoteless_idx = []
    for i in range(len(enum_sents)):
         quoteless_idx.append(re.sub(regex, str(enum_sents[i][0])+' ', enum_sents[i][1]))
    return quoteless_idx



def term_closeness(name, text, quote_idx):
    '''
    Finds the relative distance between and quote_idx in text.

    Inputs
    name: string
    text: string
    search_idx: int

    Output
    dist: tuple of name and the distance from name to quote_idx in text
    '''
    idx = text.find(quote_idx)

    forward = text[idx:idx+500].find(name)
    if forward == -1:
        forward = 1000000
    backward = text[idx:idx-500:-1].find(name[::-1])
    if backward == -1:
        backward = 1000000
    dist = min([forward, backward])

    return (name, dist)



def make_quote_df(q_ind, quote_list, n_list, idxtext):

    #Enumerate list of quotes using the index where the first sentence appears
    #Regex removes anything from the quote that isn't wrapped in quotation marks
    enumerated_quotes = list(zip([i[0] for i in q_ind],[''.join(re.findall(r'"[^"]*"',q)) for q in quote_list]))

    #Term_closeness looks for the quote index in the text, which requires a string of the numerical index
    quote_start_inds = [str(i[0]) for i in q_ind]

    names = [sorted([i[0] for i in sorted(
                            [term_closeness(name, idxtext, idx) for name in n_list],
                                                  key = lambda x: x[1], reverse = False)[:2]
                             ]) for idx in quote_start_inds]

    #Create a dataframe of names that appear near one another
    quote_df = pd.DataFrame(names, columns = ['char1','char2'])
    #append regex'd quotes to the dataframe as a column, removing quotation marks
    quote_df['quote'] = [q[1].replace('"','') for q in enumerated_quotes]
    return quote_df

def clean_text(bookfile, namefile):



    text = get_book_text(bookfile)

    text = clean_artifacts(text)

    sents = break_sentences(text)

    quote_indices = find_quote_ind(sents)

    quotes = group_quotes(sents, quote_indices)

    indexed_text = ''.join(replace_quote_with_idx(list(enumerate(sents))))

    first_names = pd.read_csv(namefile, header = None)

    first_names = set(first_names[1])

    first_names.remove('Tom')

    first_names.add('Greatjon')
    first_names.remove('Rhaegar')
    first_names.remove('High')
    first_names.remove('Nymeria')
    first_names.remove('Red')
    first_names.remove('Grey')
    first_names.add('Grey Worm')
    first_names.remove('Ben')
    first_names.remove('Val')
    for n in ['Wylis','Robett','Arys','Lyn','Jack','Jyck','Todder','Sour']:
        first_names.remove(n)
    try:
        first_names.remove('Maester')
    except:
        pass

    quote_df = make_quote_df(quote_indices, quotes, first_names,indexed_text)

    #quote_df.to_csv('../data/quotes_book-3')

    return quote_df,text,sents,quote_indices,quotes,indexed_text

if __name__ == "__main__":
    book = '../data/003ssb.txt'
    names = '../data/character_first_names.csv'
    quote_df,text,sents,quote_indices,quotes,indexed_text = clean_text(book, names)
