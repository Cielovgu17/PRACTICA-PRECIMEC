# Subir el instructivo a internet, con edición (PythonAnywhere, gratis)

Al terminar tendrás un solo link:

- `https://TU-USUARIO.pythonanywhere.com` → el instructivo, para todos.
- `https://TU-USUARIO.pythonanywhere.com/editar` → el modo edición, con la cuenta admin.

## 1. Crear la cuenta
1. Entra a <https://www.pythonanywhere.com> y pulsa **Pricing & signup**.
2. Elige **Create a Beginner account** (es gratis).
3. El **usuario** que escojas será parte del link. Por ejemplo `instructivoprecimec`.

## 2. Subir el paquete
1. Arriba, entra a **Files**.
2. Pulsa **Upload a file** y elige `instructivo-en-linea.zip` (está en la carpeta `PRÁCTICA PRECIMEC`).
3. Arriba, entra a **Consoles** → **Bash**. En la ventana negra escribe esto y pulsa Enter:

   ```
   unzip -o instructivo-en-linea.zip
   ```

## 3. Crear la página
1. Arriba, entra a **Web** → **Add a new web app** → **Next**.
2. Elige **Manual configuration** (no elijas Flask ni Django).
3. Elige **Python 3.13** (o la versión más nueva que aparezca) → **Next**.
4. En la sección **Code**, haz clic en el link del **WSGI configuration file**.
5. Borra todo lo que trae el archivo y pega esto, cambiando `TU-USUARIO` por tu usuario:

   ```python
   import os
   import sys

   path = "/home/TU-USUARIO/instructivo"
   if path not in sys.path:
       sys.path.insert(0, path)
   os.chdir(path)

   from wsgi import application
   ```

6. Pulsa **Save** (arriba a la derecha) y vuelve a la pestaña **Web**.
7. Baja hasta **Security** y activa **Force HTTPS**.
8. Arriba, pulsa el botón verde **Reload**.

## 4. Probar
- Abre `https://TU-USUARIO.pythonanywhere.com`: debe verse el instructivo.
- Abre `https://TU-USUARIO.pythonanywhere.com/editar` y entra con la cuenta admin
  (correo y contraseña en `data/credenciales-iniciales.txt`).

## Cada 3 meses
La cuenta gratis pide confirmar que sigues usando la página: entra a **Web** y pulsa
**Run until 3 months from today**. PythonAnywhere te avisa por correo antes.

## Si algo falla
En **Web**, abre el **Error log** y copia las últimas líneas a quien te ayude.
