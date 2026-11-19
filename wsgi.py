from app import create_app

app = create_app()

if __name__ == '__main__':
    # Development server; the container runs gunicorn (see Dockerfile).
    app.run(host='0.0.0.0', port=int(__import__('os').environ.get('PORT', '8082')))
