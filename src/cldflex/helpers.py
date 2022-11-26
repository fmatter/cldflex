import logging
from slugify import slugify


log = logging.getLogger(__name__)


class LexiconRetriever:
    def __init__(self):
        self.cache = {}
        self.failed_cache = set()

    def retrieve_morpheme_id(self, o, g, lex, morph_type, entry_id):
        if (o, g) in self.cache:
            return self.cache[(o, g)]
        if (o, g) in self.failed_cache:  # failing silently (except for the first try)
            return None, None
        bg = g.strip("=")
        candidates = lex[
            (lex["Form_Bare"].apply(lambda x: o in x))
            & (lex["Gloss"].apply(lambda x: bg in x))
        ]
        if len(candidates) == 1:
            m_id, sense = (
                candidates.iloc[0]["ID"],
                candidates.iloc[0]["Parameter_ID"][
                    candidates.iloc[0]["Gloss"].index(bg)
                ],
            )
            self.cache[(o, g)] = (m_id, sense)
            return (m_id, sense)
        if len(candidates) > 0:
            narrow_candidates = candidates[candidates["Type"] == morph_type]
            if len(narrow_candidates) == 1:
                return (
                    narrow_candidates.iloc[0]["ID"],
                    narrow_candidates.iloc[0]["Parameter_ID"][
                        narrow_candidates.iloc[0]["Gloss"].index(bg)
                    ],
                )
            log.warning(f"Multiple lexicon entries for {o} '{g}', using the first hit:")
            print(morph_type)
            print(candidates)
            return (
                candidates.iloc[0]["ID"],
                candidates.iloc[0]["Parameter_ID"][
                    candidates.iloc[0]["Gloss"].index(bg)
                ],
            )
        log.warning(f"No hits for /{o}/ '{g}' in lexicon ({entry_id})!")
        self.failed_cache.add((o, g))
        return None, None


empty_slugs = {}


def add_to_list_in_dict(dic, key, value):
    dic.setdefault(key, [])
    dic[key].append(value)


def slug(string):
    if slugify(string) != "":
        return slugify(string)
    if string in empty_slugs:
        return empty_slugs[string]
    c = 0
    test_string = f"null-{c}"
    while test_string in empty_slugs.values():
        c += 1
        test_string = f"null-{c}"
    empty_slugs[string] = test_string
    return test_string


def deduplicate(unreliable_list):
    return list(dict.fromkeys(unreliable_list))


def delistify(df, sep):
    for col in df.columns:
        test_df = df[df[col].apply(lambda x: isinstance(x, list))]
        if len(test_df) == 0:
            continue
        df[col] = df[col].fillna("").apply(list)
        df[col] = df[col].apply(sep.join)
    return df
