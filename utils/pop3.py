
# -*- coding: UTF-8 -*-
import base64
import datetime
import email
import poplib
import ssl
from email.header import decode_header, make_header

def get_pop3(auth):
    print('POP3 Start[ ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f') + ' ]')
    host = "pop.gmail.com"
    nego_combo = ("ssl", 995) # ("通信方式", port番号)

    if nego_combo[0] == "no-encrypt":
        popclient = poplib.POP3(host, nego_combo[1], timeout=10)
    elif nego_combo[0] == "starttls":
        context = ssl.create_default_context()
        popclient = poplib.POP3(host, nego_combo[1], timeout=10)
        popclient.stls(context)
    elif nego_combo[0] == "ssl":
        context = ssl.create_default_context()
        popclient = poplib.POP3_SSL(host, nego_combo[1], timeout=10, context=context)
    popclient.set_debuglevel(2)

    username = "nguyenhuong791123@gmail.com"
    password = "huong080"
    auth_method = "user"

    if auth_method == "user":
        popclient.user(username)
        popclient.pass_(password)
    elif auth_method == "apop":
        # Gmailはnot supported
        # yahooはnot supported
        popclient.apop(username, password)
    elif auth_method == "rpop":
        # Gmailはできない
        # yahooはできない
        popclient.rpop(username)
        popclient.pass_(password)


    download_num = 3
    msg_list = [] # 取得したMIMEメッセージを格納するリスト
    msg_num = popclient.stat()[0]  # POP3サーバに存在するメールの数を取得
    print(auth)
    if msg_num <= download_num:
        download_num = msg_num
    for i in range(download_num):
        msg_bytes = b""
        for line in popclient.retr(download_num)[1]:
            msg_bytes += line + b"\n"
        msg_list.append(email.message_from_bytes(msg_bytes))
    popclient.quit()


    # """
    # 受信したメール（MIMEメッセージ）の確認
    # """
    # for msg in msg_list:
    #     print(msg)
    #     print()

    """
    各ヘッダや本文を取得する
    """
    result = []
    for msg in msg_list:
        mail = {}
        # 各ヘッダはディクショナリのようにアクセスできる
        # from_addr = str(make_header(decode_header(msg["From"])))
        # subject = str(make_header(decode_header(msg["Subject"])))
        # print("From:{}".format(from_addr))
        # print("Subject:{}".format(subject))
        mail['from'] = str(make_header(decode_header(msg["From"])))
        mail['to'] = str(make_header(decode_header(msg["To"])))
        # mail['cc'] = str(make_header(decode_header(msg["Cc"])))
        # mail['bcc'] = str(make_header(decode_header(msg["Bcc"])))
        mail['subject'] = str(make_header(decode_header(msg["Subject"])))

        # 本文(payload)を取得する
        body = None
        if msg.is_multipart() is False:
            # SinglePartのとき
            payload = msg.get_payload(decode=True) # 備考の※1
            charset = msg.get_content_charset() # 備考の※2
            if charset is not None:
                payload = payload.decode(charset, "ignore")
            mail['body'] = payload.decode("utf-8")

        else:
            # MultiPartのとき
            for part in msg.walk():
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset()
                if charset is not None:
                    payload = payload.decode(charset, "ignore")

                val = str(payload)[2]
                if val == "b'":
                    payload = payload.decode("utf-8")
                mail['body'] = payload

        result.append(mail)
    
    return result

