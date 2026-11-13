# Instructivo en línea con edición (gratis)

Cómo queda:

- **PythonAnywhere (cuenta gratis)** guarda los textos, las cuentas y el modo edición.
  Link de edición: `https://TU-USUARIO.pythonanywhere.com/editar`
- **Vercel (gratis)** guarda las imágenes y animaciones pesadas (la cuenta gratis de PythonAnywhere
  solo tiene 512 MB) y sigue siendo el link principal: `https://practica-precimec.vercel.app`.
  Ese link muestra lo que hay en PythonAnywhere, así que al pulsar **Publicar** en el modo edición
  se actualiza solo.

## 1. Crear la cuenta (lo hace Cielo)
1. Entra a <https://www.pythonanywhere.com> → **Pricing & signup** → **Create a Beginner account** (gratis).
2. El **usuario** que escojas va en el link. Por ejemplo `instructivoprecimec`.

## 2. Subir el paquete
1. En esta carpeta ejecuta `python empaquetar.py`: crea `instructivo-en-linea.zip` (pocos MB, sin animaciones).
2. En PythonAnywhere, arriba, **Files** → **Upload a file** → elige el zip.
3. Arriba, **Consoles** → **Bash**. Escribe y pulsa Enter:

   ```
   unzip -o instructivo-en-linea.zip
   ```

## 3. Crear la página
1. **Web** → **Add a new web app** → **Next** → **Manual configuration** → **Python 3.13** (o la más nueva) → **Next**.
2. En **Code**, abre el **WSGI configuration file**, borra todo y pega (cambia `TU-USUARIO`):

   ```python
   import os
   import sys

   path = "/home/TU-USUARIO/instructivo"
   if path not in sys.path:
       sys.path.insert(0, path)
   os.chdir(path)

   from wsgi import application
   ```

3. **Save**, vuelve a **Web**, en **Security** activa **Force HTTPS** y pulsa **Reload**.

## 4. Unir el link principal
En esta carpeta:

```
python exportar.py --servidor https://TU-USUARIO.pythonanywhere.com
vercel link --yes --project practica-precimec --cwd publicar
vercel deploy --prod --yes --cwd publicar
```

(Borrar `publicar/.env.local` y `publicar/.gitignore` antes del deploy.)

## 5. Dar acceso a otra persona
Entra a `https://TU-USUARIO.pythonanywhere.com/editar` con la cuenta admin
(datos en `data/credenciales-iniciales.txt`) y crea una cuenta para esa persona con su correo.
Ella edita en ese mismo link y pulsa **Publicar**.

## Para tener en cuenta
- La cuenta gratis tiene 512 MB: alcanza para textos e imágenes nuevas, no para muchas animaciones nuevas.
  Las animaciones nuevas grandes conviene pasármelas para subirlas a Vercel.
- PythonAnywhere pide de vez en cuando confirmar que la página sigue en uso (**Web** → **Run until…**);
  avisa por correo.
- Si algo falla: **Web** → **Error log**, copiar las últimas líneas.
