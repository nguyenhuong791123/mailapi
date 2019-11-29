# -*- coding: UTF-8 -*-
import json
import imaplib, re, email, six
from .utils import *

def get_imap4(auth):
    auth['host'] = "imap.gmail.com"
    auth['port'] = "993"
    auth['username'] = "nguyenhuong791123@gmail.com"
    auth['password'] = "huong080"
    auth['box'] = "IMAP4BOX" #"INBOX"
    gmail = server(auth)
    type, [data] = gmail.search(None, "(UNSEEN)")

    if type != "OK" and is_empty(data):
        return []

    result = []
    for i in data.split():
        ok, x = gmail.fetch(i,'RFC822')
        if ok != "OK":
            continue

        msg = email.message_from_bytes(x[0][1])
        payload = None
        mail = {}
        if msg.is_multipart() is False:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset()
            if charset is not None:
                payload = payload.decode(charset, "ignore")
        else:
            for part in msg.walk():
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset()
                if charset is not None:
                    payload = payload.decode(charset, "ignore")

        print(str(payload))
        mail['content'] = payload
        result.append(mail)

    gmail.close()
    gmail.logout()
    return result

def server(auth):
    gmail = imaplib.IMAP4_SSL(auth['host'], auth['port'])
    gmail.login(auth['username'], auth['password'])
    gmail.select(auth['box'])
    return gmail