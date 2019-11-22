# -*- coding: UTF-8 -*-
import os
import base64
import smtplib
import ssl
import shutil
import datetime
import zipfile
import pyminizip
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import formatdate
from email import encoders

def receive():
    print('Receive Mail !!!')

def sendPlainText(auth, obj):
    print('Send Mail Start[ ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f') + ' ]')
    body = obj['body']
    charset = obj['charset']
    type = obj['type']
    zip = obj['zip']
    zippw = obj['zippw']

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

    outpath = None
    updir = './upload/'
    zipname = None
    if obj['files'] is not None and len(obj['files']) > 0:
        dt = datetime.datetime.now()
        dir = dt.strftime('%Y%m%d%H%M%S.%f')[:-3]
        outpath = updir + dir
        if os.path.isdir(outpath) == False:
            os.mkdir(outpath)
        for o in obj['files']:
            filename = o['name']
            outfile = outpath + '/' + filename
            convert_b64_string_to_file(o['data'], outfile)
            if zip is None or zip == False:
                ext = filename.split(".")[-1]
                if os.path.isfile(outfile):
                    attach = MIMEApplication(open(outfile, 'rb').read(), _subtype=ext)
                    attach.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(attach)

        if zip is not None and zip == True:
            os.chdir(updir)
            zipname = dir + '_zip.zip'
            if zippw is None or len(zippw) <= 0:
                with zipfile.ZipFile(zipname,'w', compression=zipfile.ZIP_STORED)as n_zip:
                    for file in os.listdir(dir):
                        n_zip.write(os.path.join(dir, file))
            else:
                src = []
                level = 4
                for file in os.listdir(dir):
                    src.append(os.path.join(dir, file))
                pyminizip.compress_multiple(src, [], zipname, zippw, level)

            os.chdir('../')
            attach = MIMEBase('application', 'zip')
            attach.set_payload(open(updir + zipname, 'rb').read())
            encoders.encode_base64(attach)
            attach.add_header('Content-Disposition', 'attachment', filename=zipname)
            msg.attach(attach)

    result = {}
    smtpclient = None
    try:
        host = auth['host'] # "smtp.gmail.com"
        nego_combo = (auth['auth'], auth['port']) # ("starttls", 587)
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

        smtpclient.login(auth['username'], auth['password'])
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
        if zip is not None and zip == True and zipname is not None and os.path.isfile(updir + zipname):
            os.remove(updir + zipname)

    print('Send Mail End[ ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f') + ' ]')
    return result

def convert_b64_string_to_file(s, outfile_path):
    with open(outfile_path, "wb") as f:
        f.write(base64.b64decode(s))