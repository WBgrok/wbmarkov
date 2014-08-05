#####
#
# Converting the non OOP based set of functions into an exportable module and set of classes
# TODO: add @staticmethod wherever needed
# TODO: Live mode is not optimal - we recalculate all probabilities rather than the ones of the objects we've just touched
# TODO: control verbosity (we print a lot when parsing)

# The generator will need this
import random

class WBMarkovError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class Parser:
    """Markov Parser Object
    This collates all the methods needed to parse text and populate the statistical model in the DB"""

    ##  SPECIAL CHARACTERS

    # TODO put in the db
    # Those are mutable class variables deliberately - it's expected they will be shared by all parsers and generators. 
    # 
    # !!! NOTE If you find yourself changng the special characters lists, you might want to put the same changes in the generator class (hence the TODO: get this from the DB)
    #
    # Special characters handling is to separate them for words so they can be handled as words in the statistical model
    # The breakdown in categories below is for the benefit of correct typesetting when generating
    # The parsing will extract special characters as long as they are in any of those lists (eg having comma as space after does not mean the parser expects input text to follow that rule)

    # A given char should only appear in at most one of those lists: generation will have stop char stuck to the last word (see below)
    special_chars_space_after = [',', ')', ':', ']', '}']
    special_chars_space_before = ['(', '[', '{']
    special_chars_space = ['"','-', "=", "&", "+"] # That's space on either side
    special_chars_no_space = ['\'', '_']
    # if found in the middle of a string, that's considered the end of a phrase
    # for generation, they'll be sripped of precending space (which may not be correct for all languages
    # Including the line break may or may not be a good idea, depending on how strings are fed.
    stop_chars = ['.', ';', '?', '!'] 

    # special_chars=[',', '\'', ':', ';', '(', ')', '.', ';',  '?', '!', '-', '_', '"', ']', '[']
    special_chars = special_chars_space_after + special_chars_space_before + special_chars_space + special_chars_no_space + stop_chars

    # the mapping of the char to itself, padded by spaces is done once for convenience
    special_chars_dict = {c: "".join([" ", c, " "]) for c in special_chars}

    # a mapping of the char as it will appear in a "naive" string, to its correct format
    # I'm told this may not work in python 3
    special_chars_tidy = dict(
        {"".join([" ", c]): c for c in special_chars_space_after + stop_chars}.items() +
        {"".join([" ", c, " "]): c for c in special_chars_no_space}.items() +
        {"".join([c, " "]): c for c in special_chars_space_before}.items()
    )

    def __init__(self, pgdbCnx, live=True, do_db_init=True):
        """ Create new Parser hooked to a specific DB. Will expect the DB schema to be present, but will by default create initial word and digram data"""

        # pgdb connection and cursor
        self.db = pgdbCnx
        self.cur = self.db.cursor()

        # this flag controls whether to update statistics as we parse.
        # For one-off big load of training data, set to false, then call calculate_all_the_calculations
        self.live_mode = live

        # Initialise the DB that we assume is empty
        if do_db_init:
            # Verify the DB is indeed not initialised
            self.cur.execute("SELECT * FROM tGlobal LIMIT 1")
            if self.cur.rowcount > 0:
                raise WBMarkovError("Failed to initalise the DB - tGlobal is empty")
            self.cur.execute("SELECT * FROM tWord LIMIT 1")
            if self.cur.rowcount > 0:
                raise WBMarkovError("Failed to initalise the DB - tWord is empty")
            self.cur.execute("SELECT * FROM tDigram LIMIT 1")
            if self.cur.rowcount > 0:
                raise WBMarkovError("Failed to initalise the DB - tDigram is empty")
            self.cur.execute("SELECT * FROM tTrigram LIMIT 1")
            if self.cur.rowcount > 0:
                raise WBMarkovError("Failed to initalise the DB - tTrigram is empty")
            # If we're here, everything is fine - insert the initialisation data
            self.cur.execute("INSERT INTO tGlobal (w_count,d_count,t_count,discount) VALUES (0,0,0,0)")
            self.cur.execute("INSERT INTO tWord (word,count,ml_prob) VALUES ('START',0,0), ('STOP',0,0)")
            self.cur.execute(""" INSERT INTO tDigram (word_1,word_2,count,ml_prob_rel,ml_prob,katz_prob)
                SELECT
                    word_id,
                    word_id,
                    0,
                    0,
                    0,
                    0
                FROM
                    tword 
                WHERE
                    word='START'""")

        # At this stage we have either a freshly initialised DB, or one that's already been filled
        # We store a set of useful PKs as instance variables.
        self.cur.execute("SELECT word_id FROM tWord WHERE word = 'START'")
        self.start_pk = self.cur.fetchone()[0]
        self.cur.execute("SELECT word_id FROM tWord WHERE word = 'STOP'")
        self.stop_pk = self.cur.fetchone()[0]
        self.cur.execute("SELECT digram_id FROM tDigram WHERE word_1=%(start_pk)d and word_2=%(start_pk)d", {"start_pk": self.start_pk})
        self.start_dg_pk = self.cur.fetchone()[0]

        self.init_pk_dict = {"w1_pk": self.start_pk, "w2_pk": self.start_pk, "d1_pk": self.start_dg_pk}
        print "Initialisation complete."
        self.log_globals()

    def log_globals(self):
        # get the global table
        self.cur.execute("SELECT * FROM tGlobal")
        row = self.cur.fetchone()

        # build a dictionnary of n-v pairs from that, and add the PKs
        glob_dict = {self.cur.description[i][0]: row[i] for i in xrange(len(row))}
        glob_dict["start_pk"] = self.start_pk
        glob_dict["stop_pk"] = self.stop_pk
        glob_dict["start_dg_pk"] = self.start_dg_pk

        print "global values"

        for pair in glob_dict.items():
            print pair[0], pair[1]

    def add_word(self, word):
        """add word to count - expects lowercase string, returns pk, """

        word_dict = {"value": word}
        if (word == "STOP"):
            print "STOP reached"
            self.cur.execute("UPDATE tWord SET count = count + 1 WHERE word_id = %(pk)d", {"pk":self.stop_pk})
            word_pk = self.stop_pk
        else:
            self.cur.execute("SELECT word_id, count FROM tWord WHERE word = %(value)s", word_dict)
            row=self.cur.fetchone()
            if row == None:
                print "Word:", word, "created"
                self.cur.execute("INSERT INTO tWord (word,count) VALUES (%(value)s, 1)", word_dict)
                # TODO  - more graceful version? cur.lastrowid doesn't seem supported
                self.cur.execute("SELECT word_id FROM tWord WHERE word = %(value)s", word_dict)
                row =self.cur.fetchone()
                word_pk = row[0]
            else:
                word_pk = row[0]
                self.cur.execute("UPDATE tWord SET count = count + 1 WHERE word_id = %(pk)d", {"pk":word_pk})
                print "Word:", word, "updated to count =", row[1] + 1
        self.db.commit()
        if self.live_mode:
            self.word_update(word_pk)
        return word_pk

    def add_digram(self, word_1_pk, word_2):
        """adds digram to count - the pk of word_1, and word_2 in lowercase - returns dictionnary of pks for w1, w2, and d """

        # print "D adding", word_1_pk, word_2
        word_2_pk = self.add_word(word_2)
        pks_dict = {"w1_pk": word_1_pk, "w2_pk": word_2_pk}
        self.cur.execute("SELECT digram_id, count FROM tDigram WHERE word_1 = %(w1_pk)d AND word_2 = %(w2_pk)d", pks_dict)
        row=self.cur.fetchone()
        if row == None:
            #print "D inserting"
            self.cur.execute("INSERT INTO tDigram (word_1,word_2,count) VALUES (%(w1_pk)d, %(w2_pk)d , 1)", pks_dict)
            # TODO  - more graceful version? cut.lastrowid doesn't seem supported
            self.cur.execute("SELECT digram_id FROM tdigram WHERE word_1 = %(w1_pk)d AND word_2=%(w2_pk)d", pks_dict)
            row =self.cur.fetchone()
            digram_pk = row[0]
            pks_dict["d1_pk"] = digram_pk
        else:
            digram_pk = row[0]
            pks_dict["d1_pk"] = digram_pk
            self.cur.execute("UPDATE tDigram SET count = count + 1 WHERE digram_id = %(d1_pk)d", pks_dict)
            #print "D updated to count =", row[1] + 1
        self.db.commit()
        
        if self.live_mode:
            self.digram_update(pks_dict)
        return pks_dict

    def add_trigram(self, pks_dict, word_3):
        """Takes in a pk dictionary for w1, w2, d1, and word_3 as lower case"""

        # print "adding trigram", pks_dict, word_3
        digram_dict = self.add_digram(pks_dict["w2_pk"],word_3)
        # That returns the pk for digram (2,3) and for w3 - the rest, we should already have
        pks_dict["d2_pk"] = digram_dict["d1_pk"]
        pks_dict["w3_pk"] = digram_dict["w2_pk"]
        self.cur.execute("SELECT trigram_id, count FROM tTrigram WHERE digram = %(d1_pk)d AND word_3=%(w3_pk)d", pks_dict)
        row=self.cur.fetchone()
        if row == None:
            print "T inserting"
            self.cur.execute("INSERT INTO tTrigram (word_1,word_2,digram,word_3,count) VALUES (%(w1_pk)d, %(w2_pk)d, %(d1_pk)d, %(w3_pk)d, 1)", pks_dict)
            # TODO  - more graceful version? cut.lastrowid doesn't seem supported
            self.cur.execute("SELECT trigram_id FROM tTrigram WHERE digram = %(d1_pk)d AND word_3=%(w3_pk)d", pks_dict)
            row =self.cur.fetchone()
            trigram_pk = row[0]
            pks_dict["t_pk"] = trigram_pk
            # print "trigram_pk = " + str(trigram_pk)
        else:
            trigram_pk = row[0]
            pks_dict["t_pk"] = trigram_pk
            self.cur.execute("UPDATE tTrigram SET count = count + 1 WHERE trigram_id = %(t_pk)d", pks_dict)
            # print "T updated to count =", row[1] + 1
        self.db.commit()

        if self.live_mode:
            self.trigram_update(pks_dict)

        # Clean up the dictionary so that it can be passed to the next trigram:
        pks_dict["w1_pk"] = pks_dict["w2_pk"]
        pks_dict["w2_pk"] = pks_dict["w3_pk"]
        pks_dict["d1_pk"] = pks_dict["d2_pk"]
        del pks_dict["d2_pk"]
        del pks_dict["w3_pk"]
        del pks_dict["t_pk"]
        return pks_dict

    def word_update(self, word_pk):
        """Updates word count and maximum likelyhood probability of a given word"""

        self.cur.execute("UPDATE tGlobal SET w_count = w_count + 1")
        #self.cur.execute("UPDATE tword SET ml_prob = count::numeric / w_count::numeric FROM tglobal WHERE word_id=%(pk)d;", {"pk":word_pk})
        self.cur.execute("UPDATE tword SET ml_prob = count::numeric / w_count::numeric FROM tglobal")
        self.db.commit()

    def digram_update(self, pks_dict):
        """updates digram count and stats for a given digram - takes in a dictionary with w1_pk, w2_pk, d1_pk"""

        #print "pks_dict", pks_dict
        #print "updating global count"
        self.cur.execute("UPDATE tGlobal SET d_count = d_count + 1")
        #print "updating ml_prob"
        #self.cur.execute("UPDATE tDigram SET ml_prob = count::numeric / d_count::numeric FROM tGlobal WHERE digram_id = %(d1_pk)d", pks_dict)
        self.cur.execute("UPDATE tDigram SET ml_prob = count::numeric / d_count::numeric FROM tGlobal")
        #print "updating ml_prob_rel"
        #self.cur.execute("UPDATE tDigram SET ml_prob_rel = tDigram.count::numeric / tWord.count::numeric FROM tWord WHERE digram_id = %(d1_pk)d AND word_id = %(w1_pk)d", pks_dict)
        self.cur.execute("UPDATE tDigram SET ml_prob_rel = tDigram.count::numeric / tWord.count::numeric FROM tWord WHERE word_id = word_1")
        self.db.commit()

    def trigram_update(self, pks_dict):
        """updates trigram count and stats - takes in a dictionary with pks for w1, w2, w3, t, d1 and d2"""

        #print "pks_dict", pks_dict
        #print "updating global count"
        self.cur.execute("UPDATE tGlobal SET t_count = t_count + 1")
        #print "updating ml_prob"
        #self.cur.execute("UPDATE tTrigram SET ml_prob = count::numeric / t_count::numeric FROM tGlobal WHERE trigram_id = %(t_pk)d", pks_dict)
        self.cur.execute("UPDATE tTrigram SET ml_prob = count::numeric / t_count::numeric FROM tGlobal")
        #print "updating ml_prob_rel"
        #self.cur.execute("UPDATE tTrigram SET ml_prob_rel = tTrigram.count::numeric / tDigram.count::numeric FROM tDigram WHERE digram_id = %(d1_pk)d AND trigram_id = %(t_pk)d", pks_dict)
        self.cur.execute("UPDATE tTrigram SET ml_prob_rel = tTrigram.count::numeric / tDigram.count::numeric FROM tDigram WHERE digram_id = digram")
        self.db.commit()

    def calculate_all_the_calculations(self):
        """tallies up count and works out probabilities """

        if self.live_mode:
            print "Not running retroactive calculation in live mode"
            return
        print "Tallying up global totals"
        self.cur.execute("UPDATE tGlobal SET w_count = (SELECT SUM(count) FROM tWord)")
        self.cur.execute("UPDATE tGlobal SET d_count = (SELECT SUM(count) FROM tDigram)")
        self.cur.execute("UPDATE tGlobal SET t_count = (SELECT SUM(count) FROM tTrigram)")
        self.db.commit()
        self.log_globals()

        print "Working out prob for each word"
        self.cur.execute("UPDATE tword SET ml_prob = count::numeric / w_count::numeric FROM tglobal")
        print "Updated", self.cur.rowcount
        self.db.commit()
        print "Working out prob for Digrams"
        self.cur.execute("UPDATE tDigram SET ml_prob = count::numeric / d_count::numeric FROM tGlobal")
        self.cur.execute("UPDATE tDigram SET ml_prob_rel = tDigram.count::numeric / tWord.count::numeric FROM tWord WHERE word_id = word_1")
        print "Updated", self.cur.rowcount
        self.db.commit()
        print "Working out prob for Trigrams"
        self.cur.execute("UPDATE tTrigram SET ml_prob = count::numeric / t_count::numeric FROM tGlobal")
        self.cur.execute("UPDATE tTrigram SET ml_prob_rel = tTrigram.count::numeric / tDigram.count::numeric FROM tDigram WHERE digram_id = digram")
        self.db.commit()
        print "Updated", self.cur.rowcount

    def prepare_string(self, st):
        """splits a string into a list of words - special characters are considered words"""

        # case and whitespace
        st = st.lower()
        st = st.replace("\t"," ")
        # Substitute special chars - we don't worry about multiple spaces
        for c in self.special_chars:
            st=st.replace(c,self.special_chars_dict[c])

        # split by spaces, strip empty any empty strings generated by multiple spaces
        ret = st.split(' ')
        ret[:] = [w for w in ret if w != ""]
        return ret

    def extract_first_phrase(self, ls):
        """takes in a list of words, potentially several phrases, returns the first phrase, and removes it from ls"""

        ret = []
        while len(ls) > 0:
            w = ls.pop(0)
            ret.append(w)
            if w in self.stop_chars:
                print "spliting on", w
                return ret

        # If we reach this point, the list is a single phrase (the last of the list), return it
        return ret

    def extract_all_phrases(self, l):
        """takes in a list of words, potentially several phrases, returns a list of one-phrase lists - leaves l empty"""

        ret = []
        while l != []:
            p = self.extract_first_phrase(l)
            if p != []:
                ret.append(p)
            print "phrases found", len(ret)
        return ret

    def initial_phrase_load(self):
        """At the beginning of a phrase, we increment counts of START and their digram"""

        pks_dict = self.init_pk_dict.copy()
        self.cur.execute("UPDATE tWord SET count = count + 2 WHERE word_id=%(w1_pk)d", pks_dict)
        self.cur.execute("UPDATE tDigram SET count = count +1 WHERE digram_id = %(d1_pk)d", pks_dict)
        if self.live_mode:
            self.word_update(self.start_pk)
            self.word_update(self.start_pk)
            self.digram_update(pks_dict)
        print "initial_phrase_load " + str(pks_dict)
        return pks_dict

    def parse_phrase(self, lst):
        """processes a list of individual words (without stop nor start) """

        pks_dict = self.initial_phrase_load()
        lst.append("STOP")
        for w in lst:
            pks_dict = self.add_trigram(pks_dict,w)

    def log_pks_dict(self, pks_dict):
        """Prints out word values from a dict of w1, w2, d primary keys"""

        self.cur.execute("SELECT tw1.word w1_actual, tw2.word w2_actual, d.w1 d_w1, d.w2 d_w2 FROM tWord tw1, tWord tw2, vDigram d WHERE tw1.word_id = %(w1_pk)d AND tw2.word_id = %(w2_pk)d AND d.digram_id = %(d1_pk)d", pks_dict)
        row =self.cur.fetchone()
        values = {self.cur.description[i][0]: row[i] for i in xrange(len(row))}
        print "values for pks_dict", pks_dict
        for pair in values.items():
            print pair[0], pair[1]

    def parse_string(self, s):
        """feed an unformatted string to the system - will handle line breaks"""

        l = self.prepare_string(s)
        l = self.extract_all_phrases(l)
        for p in l:
            self.parse_phrase(p)

    def parse_file(self, filename):
        """Feeds the whole file to the model (forces non-live mode)"""

        self.live_mode = False
        
        f = open(filename)
        s = f.readline()
        i = 0
        while (s != ''):
            i += 1
            print "Parsing line", i
            self.parse_string(s)
            s = f.readline()
        print "Parsed", i, "lines"
        self.calculate_all_the_calculations()

class Generator:
    """ Generator Object
    Can generate random, legit-looking phrases based on a statistical trigram model DB"""

    ##  SPECIAL CHARACTERS

    # TODO put in the db
    # Those are mutable class variables deliberately - it's expected they will be shared by all parsers and generators.
    # 
    # !!! NOTE If you find yourself changng the special characters lists, you might want to put the same changes in the Parser class (hence the TODO: get this from the DB)
    #
    # Special characters handling is to separate them for words so they can be handled as words in the statistical model
    # The breakdown in categories below is for the benefit of correct typesetting when generating
    # The parsing will extract special characters as long as they are in any of those lists (eg having comma as space after does not mean the parser expects input text to follow that rule)

    # A given char should only appear in at most one of those lists: generation will have stop char stuck to the last word (see below)
    special_chars_space_after = [',', ')', ':', ']', '}']
    special_chars_space_before = ['(', '[', '{']
    special_chars_space = ['"','-', "=", "&", "+"] # That's space on either side
    special_chars_no_space = ['\'', '_']
    # if found in the middle of a string, that's considered the end of a phrase
    # for generation, they'll be sripped of precending space (which may not be correct for all languages
    # Including the line break may or may not be a good idea, depending on how strings are fed.
    stop_chars = ['.', ';', '?', '!'] 

    # special_chars=[',', '\'', ':', ';', '(', ')', '.', ';',  '?', '!', '-', '_', '"', ']', '[']
    special_chars = special_chars_space_after + special_chars_space_before + special_chars_space + special_chars_no_space + stop_chars

    # the mapping of the char to itself, padded by spaces is done once for convenience
    special_chars_dict = {c: "".join([" ", c, " "]) for c in special_chars}

    # a mapping of the char as it will appear in a "naive" string, to its correct format
    # I'm told this may not work in python 3
    special_chars_tidy = dict(
        {"".join([" ", c]): c for c in special_chars_space_after + stop_chars}.items() +
        {"".join([" ", c, " "]): c for c in special_chars_no_space}.items() +
        {"".join([c, " "]): c for c in special_chars_space_before}.items()
    )

    def __init__(self, pgdbCnx):
        """ Create a new generator fed by a specific model (a specific DB - pass the db connection to this constructor)"""

        # pgdb connection and cursor
        self.db = pgdbCnx
        self.cur = self.db.cursor()

        # Verify the DB is initialised 
        self.cur.execute("SELECT * FROM tGlobal LIMIT 1")
        if self.cur.rowcount == 0:
            raise WBMarkovError("Failed to initalise the DB - tGlobal is empty")
        self.cur.execute("SELECT * FROM tWord LIMIT 1")
        if self.cur.rowcount == 0:
            raise WBMarkovError("Failed to initalise the DB - tWord is empty")
        self.cur.execute("SELECT * FROM tDigram LIMIT 1")
        if self.cur.rowcount == 0:
            raise WBMarkovError("Failed to initalise the DB - tDigram is empty")
        self.cur.execute("SELECT * FROM tTrigram LIMIT 1")
        if self.cur.rowcount == 0:
            raise WBMarkovError("Failed to initalise the DB - tTrigram is empty")

        # If we're here, everything is fine - get the PK of the (START,START) digram
        self.cur.execute("SELECT word_id FROM tWord WHERE word = 'START'")
        self.start_pk = self.cur.fetchone()[0]
        self.cur.execute("SELECT digram_id FROM tDigram WHERE word_1=%(start_pk)d and word_2=%(start_pk)d", {"start_pk": self.start_pk})
        self.start_dg_pk = self.cur.fetchone()[0]

        # Seed the random module
        random.seed()

    def get_candidate_words(self, digram_id):
        """Return a list of pairs - each potential trigram with cumulative count"""

        ret = []
        d = 0
        # select prob and word pk from trigrams for digram
        self.cur.execute("SELECT count, trigram_id FROM tTrigram WHERE digram = %(dg)d", {"dg": digram_id})
        row = self.cur.fetchone()
        while (row != None):
            d += row[0]
            ret.append([d, row[1]])
            row = self.cur.fetchone()
        # print "get_candidate_words " + str(ret)
        return ret


    def pick_word(self, distrib):
        """Takes in a distribution (list of pairs [density,tg_id]) returns randomly chosen trigram"""

        r = random.uniform(0, distrib[len(distrib) - 1][0])
        for p in distrib:
            if (p[0] >= r):
                # print "pick_word " + str(p[1])
                return p[1]
        raise WBMarkovError("Error getting the random word - random.uniform appears to have returned a value larger than the index of the last candidate")

    def pick_next_word(self, digram):
        """Given a digram, returns a pair with the new digram and random next word """

        t_pk = self.pick_word(self.get_candidate_words(digram))
        self.cur.execute("SELECT d.digram_id, w.word FROM tdigram d, tword w, ttrigram t WHERE t.trigram_id = %(t_pk)d and t.word_2 = d.word_1 and t.word_3 = d.word_2 and w.word_id = t.word_3", {"t_pk": t_pk})
        ret = self.cur.fetchone()
        # print "pick_next_word " + str(ret)
        return ret


    def gen_phrase(self):
        """Returns a list of words randomly generated from the model"""

        d = self.start_dg_pk
        p = self.pick_next_word(d)
        l = []
        while (p[1] != "STOP"):
            l.append(p[1])
            p = self.pick_next_word(p[0])
        # print "gen_phrase " + str(l)
        return l


    def post_process(self, phrase):
        """Takes in a phrase as list of chars and returns a 'cleaned up' string"""

        st = ' '.join(phrase)
        for c in self.special_chars_tidy:
            st=st.replace(c,self.special_chars_tidy[c])
        return st

    def gen_phrase_string(self):
        """ Generates a random phrase string"""
        return self.post_process(self.gen_phrase())