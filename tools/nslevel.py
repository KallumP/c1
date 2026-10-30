"""
Read (and later write) the game's level files: a level is an .nsd (page
table and level header) and an .nsf (64 KB pages of entries).
"""
import struct

MAGIC_PAGE = 0x1234
MAGIC_ENTRY = 0x100FFFF
PAGE_SIZE = 0x10000
SECTOR_SIZE = 0x800
EID_NONE = 0x6396347F


def eid_to_str(eid):
    return ""


def str_to_eid(name):
    return 0


def read_nsd(data):
    return None


def read_pages(nsf, page_count, pages_offset=0):
    return []


def read_level(streams_dir, lid):
    return None


def count_by_type(pages):
    return {}
