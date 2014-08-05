-- A quirky bit of code by Will Berard
-- https://github.com/WBgrok/wbmarkov

-- General stuff
DROP TABLE tGlobal CASCADE;
CREATE TABLE tGlobal (
    w_count  INTEGER DEFAULT 0 NOT NULL,
    d_count  INTEGER DEFAULT 0 NOT NULL,
    t_count  INTEGER DEFAULT 0 NOT NULL,
    discount NUMERIC(6,4) DEFAULT 0 NOT NULL
);

-- Words
DROP TABLE tWord CASCADE;
CREATE TABLE tWord (
    word_id SERIAL NOT NULL PRIMARY KEY,
    word    VARCHAR(30) NOT NULL UNIQUE,
    count   INTEGER DEFAULT 1 NOT NULL,
    ml_prob NUMERIC DEFAULT 0 NOT NULL-- tWord.count / tGlobal.w_count
);

-- Digrams
DROP TABLE tDigram CASCADE;
CREATE TABLE tDigram (
    digram_id SERIAL NOT NULL PRIMARY KEY,
    word_1 INTEGER NOT NULL REFERENCES tWord (word_id), -- previous word
    word_2 INTEGER NOT NULL REFERENCES tWord (word_id), -- current word  - ie p is p(w2|w1)
    count  INTEGER NOT NULL DEFAULT 1 NOT NULL,
    ml_prob_rel NUMERIC DEFAULT 0 NOT NULL, -- relative probability of w2 given w1 (count/tWord.count for w1)
    ml_prob     NUMERIC DEFAULT 0 NOT NULL, -- absolute probability of occurence (count/tGlobal.d_count)
    katz_prob   NUMERIC DEFAULT 0 NOT NULL, -- katz back-off prob (based on tGlobal.discount)
    UNIQUE (word_1,word_2)
);
CREATE INDEX iDigram_x1 on tDigram (word_1);

--Trigrams
DROP TABLE tTrigram CASCADE;
CREATE TABLE tTrigram (
    trigram_id SERIAL PRIMARY KEY,
    word_1 INTEGER NOT NULL REFERENCES tWord (word_id), -- de-normalised - first and second word
    word_2 INTEGER NOT NULL REFERENCES tWord (word_id), -- are from the digram
    digram INTEGER NOT NULL REFERENCES tDigram (digram_id),
    word_3 INTEGER NOT NULL REFERENCES tWord (word_id),
    count  INTEGER NOT NULL DEFAULT 1 NOT NULL,
    ml_prob_rel NUMERIC DEFAULT 0 NOT NULL, -- relative probability of w3 given the digram (count/tDigram.count)
    ml_prob     NUMERIC DEFAULT 0 NOT NULL, -- absolute probability of occurence (count/tGlobal.t_count)
    katz_prob   NUMERIC DEFAULT 0 NOT NULL, -- katz back-off prob (based on tGlobal.discount)
    UNIQUE (digram,word_3)
);
CREATE INDEX iTrigram_x1 on tTrigram (digram);

-- Views for ease of checking

CREATE VIEW vDigram AS
    SELECT
        d.digram_id,
        w1.word as w1,
        w2.word as w2,
        d.count,
        d.ml_prob_rel,
        d.ml_prob
    FROM
        tdigram d,
        tword w1,
        tword w2
    WHERE
        d.word_1 = w1.word_id AND
        d.word_2 = w2.word_id
    ORDER BY word_1,word_2 ASC;

CREATE VIEW vTrigram AS
    SELECT
        t.trigram_id,
        t.digram,
        w1.word w1,
        w2.word w2,
        w3.word w3,
        t.count,
        t.ml_prob_rel,
        t.ml_prob
    FROM
        ttrigram t,
        tword w1,
        tword w2,
        tword w3
    WHERE
        t.word_1 = w1.word_id AND
        t.word_2 = w2.word_id AND
        t.word_3 = w3.word_id
    ORDER BY word_1,word_2 ASC;

