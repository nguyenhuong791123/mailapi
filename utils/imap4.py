import imaplib, re, email, six
from .utils import *

def get_imap4(auth):
    auth['host'] = "imap.gmail.com"
    auth['port'] = "993"
    auth['username'] = "nguyenhuong791123@gmail.com"
    auth['password'] = "huong080"
    auth['box'] = "IMAP4BOX"
    # auth['label'] = "IMAP4BOX"
    gmail = server(auth)

    e_mail_default_encoding = 'iso-2022-jp'
    type, [data] = gmail.search(None, "(UNSEEN)")

    if type != "OK" and is_empty(data):
        return []

    for i in data.split():
        ok, x = gmail.fetch(i,'RFC822')
        if ok != "OK":
            continue

        print(ok)
        ms = email.message_from_bytes(x[0][1])
        payload = ms.get_payload(decode=True)
        if payload is None:
            continue
        charset = ms.get_content_charset()
        if charset is not None:
            payload = payload.decode(charset, "ignore")

        print(payload)

    gmail.close()
    gmail.logout()

def server(auth):
    gmail = imaplib.IMAP4_SSL(auth['host'], auth['port'])
    gmail.login(auth['username'], auth['password'])
    gmail.select(auth['box'])
    # gmail.select(auth['label'])
    return gmail