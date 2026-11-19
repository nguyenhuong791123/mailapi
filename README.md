# mailapi

SMTP でメールを送信し、IMAP / POP3 でメールを読む API（Flask）。

## 起動

```sh
# リポジトリのルート（hv）で。テスト用メールサーバー mailpit も起動します
docker compose up -d --build mailapi
curl http://localhost:8082/health        # {"status":"ok"}
```

- 受信したメールは mailpit の画面で確認できます: http://localhost:8025
- 設定は `mailapi/.env`（`.env.example` を参照）。
- メールサーバーのアカウントは、ログインユーザーのテナント（トークンの `client_id`）の **サーバー情報 > メールサーバー**（tenant DB の `server`: type 1、email_type 0 = SMTP / 1 = POP3）から取得します。
  API サーバー（be）の `GET /internal/mail-servers/<tenant>` を `SERVER_SETTINGS_URI` と共有シークレット `INTERNAL_API_SECRET`（be と同じ値）で呼び、`SERVER_SETTINGS_TTL` 秒キャッシュします。
  暗号化: `tls` → STARTTLS、`ssl` → SSL、`none` → 暗号化なし。IMAP はテナントごとには設定しません。
  `SERVER_SETTINGS_URI` が空のときだけ、環境変数 `MAIL_*` のアカウントを全テナントで使います。

コンテナを使わない場合:

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt     # pyminizip のビルドに C コンパイラと zlib が必要
set -a && . ./.env && set +a
python wsgi.py                           # http://localhost:8082
python -m pytest -q tests
```

## 認証

`/` と `/health` 以外は、トークンサーバー（wso2）が発行したアクセストークンが必要です。

```
Authorization: Bearer <access_token>
```

検証方法は API サーバー（be）と同じです（`JWT_JWKS_URI` / `JWT_PUBLIC_KEY` / `JWT_SECRET`、`JWT_ISSUER`、`JWT_AUDIENCE`）。
`AUTH_REQUIRED=false` は、トークンサーバーなしで試す場合だけに使ってください。

## API

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/health` | 稼働確認 |
| POST | `/send` | メール送信 |
| POST | `/imap4` | IMAP 受信（既定は未読、既読にはしない） |
| POST | `/pop3` | POP3 受信（サーバーに残す） |

### POST /send

```json
{
  "mails": [{
    "from": "EDU <noreply@example.com>",
    "to": "a@example.com, b@example.com",
    "cc": "", "bcc": "audit@example.com",
    "subject": "件名", "body": "<p>本文</p>",
    "type": "html", "charset": "utf-8",
    "zip": true, "zippw": "1234",
    "files": [{"filename": "案内.pdf", "data": "<base64>"}]
  }]
}
```

- `type`: `plain`（既定）/ `html`（テキスト版も自動で付けます）
- `charset`: `utf-8`（既定）/ `iso-2022-jp`
- `zip: true` で添付を 1 つの `attachments.zip` にまとめます。`zippw` があればパスワード付き（Windows / macOS 標準機能で開ける ZipCrypto）
- `bcc` はヘッダーに出さず、配送先だけに入れます
- 結果: `{"result": [{"flag": true, "msg": "...", "messageId": "<...>"}]}`（メールごと。不正なメールは送らずに `flag: false`）
- 以前の `auth`（サーバーのアカウント）はリクエストからは受け付けません（無視します）

### POST /imap4

`{"mailbox": "INBOX", "limit": 20, "unseen": true}`（すべて任意）→ `{"result": [{uid, from, to, subject, date, content, attachments}]}`

### POST /pop3

`{"limit": 10}`（任意）→ `{"result": [{number, from, to, subject, date, content, attachments}]}`

## 主な設定（環境変数）

| 変数 | 既定 | 内容 |
|---|---|---|
| `MAIL_SMTP_HOST` / `_PORT` / `_SECURITY` / `_USER` / `_PASSWORD` | – / 587 / starttls | SMTP。`_SECURITY` は `ssl` / `starttls` / `none` |
| `MAIL_IMAP_*`, `MAIL_POP3_*` | 993 / 995, ssl | 未設定の `HOST` は無効（503）。アカウントは既定で SMTP と同じ |
| `MAIL_IMAP_MAILBOX` | INBOX | |
| `CORS_ORIGINS` | なし | ブラウザから呼べるオリジン（カンマ区切り、正規表現可） |
| `MAIL_MAX_MAILS` / `MAIL_MAX_RECIPIENTS` / `MAIL_MAX_FETCH` / `MAX_CONTENT_MB` | 20 / 50 / 100 / 25 | 上限 |
