# A quirky bit of code by Will Berard
# https://github.com/WBgrok/wbmarkov

# Example usage of the Markov model - assumes you have Postgres running, the schema loaded (but no data in the DB) and some way of getting python to talk to Postgres

import pgdb as dbapi2
import wbmarkov

# replace those with what's needed
# at the moment, it's one DB per model - do bear this in mind when playing around - you might want to load Lovecraft in a different DB than the Bible...
PG_DB   = "markov"
PG_HOST = "localhost"
PG_USER = "will"

_db  = dbapi2.connect(database=PG_DB, host=PG_HOST,user=PG_USER)

# Create the parser, passing it the DB connection - this will expect an empty DB, and throw an error otherwise
my_parser = wbmarkov.Parser(_db)

# If you'd like to add to an existing model, you want somethinglike
# my_parser = wbmarkov.Parser(_db, True, False)

# This will disable "live mode" (meaning the stats calculation are done in one go at the end as opposed to after each insert/update), and load up the whole file
my_parser.parse_file("sample_texts/cthulhu.txt")

# You will see a lot of stuff being printed out, as we insert object, and then the final step is a probability calculation, which should return some figures. 
# This may take a while depending on the size of your text file - feel free to have a look at the data coming into postgres in the meantime.

# Input sanitisation is paramount - the parser will do its best to deal with sprecial characters, etc, but it reads the file line by line, so the endline is considered to be the end of a sentence.
# Most text files will not follow that convention if they have hard wrap. The parser deals with whitespace gracefully, but we're going to sanitize it at this stage - the assumption is you've got something
# along the lines of the mountains_original.txt file, so with leading whitespace, and empty lines in between paragraphs. The plan is to convert line breaks to spaces, but we don't want a one-line file
# because Python whould have to read the whole file as a single line. So we're going to strip line breaks, and then re-add them, with one line per paragraph. The assumption here is that human writers
# will always end a paragraph a the end of a sentence... 

# If the text you have doesn't follow this convention, you can always go through it and add blank lines where needed...

# So, to correct this, based oun the mountains.txt example, we can do the the following in vim (*):
# Replace all whistespace by spaces (just in case we've got tabs for some reason)
# :%s/\s/ /g
# Remove all spaces from the beginning of lines (empty or not)
# :%s/^ [ ]*\(.*\)$/\1/g
# Remove all spaces from the end of lines
# :%s/^\(.*\)[ ]*$/\1/g
# Collapse all multiple spaces to single ones (this is slightly unnecessary, but doesn't do any harm)
# :%s/ [ ]*/ /g
# This is the kicker - we know we've got no legitimate double spaces - we're going to turn line breaks into spaces (having trimmed spaces from the start and end)
# But only for lines that are not empty:
# :%s/\(.\)\n/\1 /g

# if you apply the following to mountains_original.txt, you should end up with somethin that looks like mountains.txt


# (*) I tried doing it all in sed first, but vim will allow you to do replacemens on "\n", whereas sed won't - well, won't easily. There's a way around this using tr, so in the future I may provide a script for text sanitation.


###### Now for the fun bit!

# Having populated the model, we can use the generator to create sentences that match it.

my_generator = wbmarkov.Generator(_db)
for i in range(0, 100):
    print my_generator.gen_phrase_string()

