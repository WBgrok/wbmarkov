=============================
 Markov Language Model
=============================
Author: Will Berard (https://github.com/WBgrok/)

A statistical language model engine based on Markov trigrams.
Inspired by the excellent Natural Language Processing Coursera module
https://www.coursera.org/course/nlangp

The engine is in Python, with the model itself being stored in a PostgreSQL DB.
The model is populated by feeding the parser sample text. Statistical properties
of the text are then stored in the model.

This can then be used for all sorts of things, although really the main use is to
generate random phrases that statistically match the sample text.
A similar technique is for instance used by http://what-would-i-say.com/ although
that only uses bigram and unigrams, whereas this engine uses trigrams.

Installation
============

You will need PostgreSQL installed and running, as well as a way to get python to talk to Postgres.

Create a DB and load the schema.
- You can do this by hand, loading schema.sql in an empty DB
- alternatively there's an install.sh that will do this for you, eg:
-- specifying the DB name:``./install.sh -d mymarkov``
-- the script can also take in hostname, port and username: ``./install.sh -h mydbserver -p 1243 -u user -d mymarkov``

Usage
=====

See example.py for example uses. Typically, you would:

1) Populate the model
- import wbmarkov
- connect to the model DB
- create a parser object, passing a dbapi2 connection object
- get the parser to parse individual strings (eg. if hooking this to a chatbot)
- get the parser to parse and load a text file

2) Generate some stuff
- import wbmarkov
- connect to the model DB
- create a generator object, passing a dbapi2 connection object
- generate some strings (and pipe them out to your IRC or twitterbot, etc...)

3) Use it for other purposes
The engine does not support this (it's mainly geared towards generating gobbledygook),
but a populated model will give you word, digram and trigram stats for whatever you fed it.
You can then use this to work out statistical properties of the sample text, check its accuracy
working out its (delightfully named) perplexity (http://en.wikipedia.org/wiki/Perplexity) or use
it to check how close a given text matches the model (eg. to identify an author).