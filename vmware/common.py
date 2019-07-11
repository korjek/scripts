#!/usr/bin/python

import ConfigParser


def config_parser(config_file, section):
    """
    Returns dict from parsed file and section 
    """
    config = ConfigParser.ConfigParser()
    if config.read(config_file):
        data = dict(config.items(section))
        return data
    return None


