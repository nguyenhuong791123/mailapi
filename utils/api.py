# -*- coding: UTF-8 -*-
import os
import base64
import smtplib
import ssl
import shutil
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders

def receive():
    print('Receive Mail !!!')

def sendPlainText(obj):
    body = obj['body']
    charset = obj['charset']
    type = obj['type']

    msg = MIMEMultipart()
    if type == 'html':
        msg = MIMEMultipart('alternative')

    plain = None
    html = None
    if charset == "utf-8":
        plain = MIMEText(body, "plain", charset)
        if type == 'html':
            html = MIMEText(body, 'html', charset)
    elif charset == "iso-2022-jp":
        plain = MIMEText(base64.b64encode(body.encode(charset, "ignore")), "plain", charset)
        if type == 'html':
            html = MIMEText(base64.b64encode(body.encode(charset, "ignore")), "html", charset)

    plain.replace_header("Content-Transfer-Encoding", "base64")
    msg.attach(plain)
    if type == 'html':
        html.replace_header("Content-Transfer-Encoding", "base64")
        msg.attach(html)

    msg["Subject"] = obj['subject']
    msg["From"] = obj['from']
    msg["To"] = obj['to']
    msg["Cc"] = obj['cc']
    msg["Bcc"] = obj['bcc']
    msg["Date"] = formatdate(localtime = True)
    print(msg)

    outpath = None
    # if obj['files'] is not None and len(obj['files']) > 0:
    #     dt = datetime.datetime.now()
    #     outpath = './upload/' + dt.strftime('%Y%m%d%H%M%S.%f')[:-3]
    #     if os.path.isdir(outpath) == False:
    #         os.mkdir(outpath)
    #     for o in obj['files']:
    #         outfile = outpath + '/' + o['name']
    #         convert_b64_string_to_file(o['data'], outfile)
    #         if os.path.isfile(outfile):
    #             msg.set_payload(open(outfile, 'rb').read())
    #             msg.add_header('Content-Disposition', 'attachment; filename=' + o['name'])

    result = {}
    smtpclient = None
    try:
        host = "smtp.gmail.com"
        nego_combo = ("starttls", 587)
        if nego_combo[0] == "no-encrypt":
            smtpclient = smtplib.SMTP(host, nego_combo[1], timeout=10)
        elif nego_combo[0] == "starttls":
            smtpclient = smtplib.SMTP(host, nego_combo[1], timeout=10)
            smtpclient.ehlo()
            smtpclient.starttls()
            smtpclient.ehlo()
        elif nego_combo[0] == "ssl":
            context = ssl.create_default_context()
            smtpclient = smtplib.SMTP_SSL(host, nego_combo[1], timeout=10, context=context)
        smtpclient.set_debuglevel(2)

        username = "nguyenhuong791123@gmail.com"
        password = "huong080"
        smtpclient.login(username, password)

        smtpclient.send_message(msg)
        result['flag'] = True
        result['msg'] = obj['from'] + 'から' + obj['to'] + 'へメールを送信しました。'

    except Exception as e:
        result['flag'] = False
        result['msg'] = str(e)
    finally:
        if smtpclient is not None:
            smtpclient.quit()
        if outpath is not None and os.path.isdir(outpath):
            shutil.rmtree(outpath)

    return result

def convert_b64_string_to_file(s, outfile_path):
    with open(outfile_path, "wb") as f:
        f.write(base64.b64decode(s))