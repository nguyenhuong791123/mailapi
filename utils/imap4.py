import imaplib, re, email, six

def get_imap4(auth):
    auth['host'] = "imap.gmail.com"
    auth['port'] = "993"
    auth['username'] = "nguyenhuong791123@gmail.com"
    auth['password'] = "huong080"
    auth['box'] = "INBOX"
    auth['label'] = "IMAP4BOX"
    gmail = server(auth)

    e_mail_default_encoding = 'iso-2022-jp'
    type, [data] = gmail.search(None, "(UNSEEN)")
    count = 1

    if type == "OK":
        if data != '':
            print("New Mail")
        else:
            print("Non")

    for i in data.split():
        ok, x = gmail.fetch(i,'RFC822')
        print(ok)
        print(x)
        ms = email.message_from_bytes(x[0][1])
        # ms = email.message_from_string(x[0][1].decode('iso-2022-jp'))
        payload = ms.get_payload(decode=True)
        if payload is None:
            continue
        charset = ms.get_content_charset()
        if charset is not None:
            payload = payload.decode(charset, "ignore")

        # ms = email.message_from_string(x[0][1].decode('iso-2022-jp'))
        # maintext = ms.get_payload()
        print(payload)

    gmail.close()
    gmail.logout()
    #     print("カウント=",count)
    #     count+=1    
    #     result, d = gmail.fetch(num,"(RFC822)")
    #     raw_email = d[0][1]

    #     #文字コード取得
    #     msg = email.message_from_string(raw_email.decode('utf-8'))
    #     msg_encoding = email.header.decode_header(msg.get('Subject'))[0][1] or 'iso-2022-jp'

    #     #パースして解析準備
    #     msg = email.message_from_string(raw_email.decode(msg_encoding))


    # #差出人情報を取得
    #     fromObj = email.header.decode_header(msg.get('From'))
    #     addr = ""
    #     for f in fromObj:
    #         if isinstance(f[0],bytes):
    #             addr += f[0].decode(msg_encoding)
    #         else:
    #             addr += f[0]
    #         print(addr)

    # #件名の取得＆表示
    #     subject = email.header.decode_header(msg.get('Subject'))
    #     title = ""
    #     for sub in subject:
    #         if isinstance(sub[0],bytes):
    #             title += sub[0].decode(msg_encoding)
    #         else:
    #             title += sub[0]
    #         print(title)

def server(auth):
    # host = "imap.gmail.com"
    # port = 993
    # user = "nguyenhuong791123@gmail.com"
    # password = "huong080"

    gmail = imaplib.IMAP4_SSL(auth['host'], auth['port'])
    gmail.login(auth['username'], auth['password'])
    # gmail.select(auth['box'])
    gmail.select(auth['label'])
    return gmail