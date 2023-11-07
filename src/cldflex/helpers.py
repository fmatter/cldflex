import logging

import pandas as pd
from slugify import slugify

log = logging.getLogger(__name__)


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
    with pd.option_context("mode.chained_assignment", None):
        for col in df.columns:
            test_df = df[df[col].apply(lambda x: isinstance(x, list))]
            if len(test_df) == 0:
                continue
            df[col] = df[col].fillna("").apply(list)
            df[col] = df[col].apply(sep.join)
    return df


def listify(df, column, sep):
    if not isinstance(df[column].iloc[0], list):
        df[column] = df[column].apply(lambda x: x.split(sep))
    return df
