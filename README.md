# Plataforma de instructivo quirúrgico PRECIMEC (fase 1)

Instructivo interactivo de la técnica de clavo cefalomedular, con modo administrador.
Todo el contenido clínico actual es de ejemplo y debe reemplazarse por información aprobada.

## Cómo abrirla

Requiere Python 3.11 o superior. No hay que instalar nada más.

Haz doble clic en `iniciar.bat`, o ejecuta `python server.py`, y abre <http://127.0.0.1:8000>.

Quien consulta el instructivo no necesita ingresar: va integrado en el LMS y el avance se
guarda en su navegador.

Para editar, abre <http://127.0.0.1:8000/admin>. La primera vez se crea
`data/credenciales-iniciales.txt` con la cuenta de administrador; cambia la contraseña en **Mi cuenta**.

## Cómo administrar el contenido

- **Agregar un paso o subpaso:** en *Pasos y subpasos*, usa los campos «Título del nuevo paso»
  y «Nuevo subpaso». Con las flechas se cambia el orden, y el selector mueve un subpaso a otro paso.
- **Editar el contenido:** haz clic en el nombre del paso. Allí también se asigna el instrumental.
- **Publicar:** los cambios quedan en un borrador. *Previsualizar* los muestra solo a ti;
  *Publicar* los hace visibles para todas las personas.

## Cómo incorporar modelos 3D y animaciones

1. En *Modelos y archivos*, sube el archivo (STL, GLB o GLTF autocontenido, hasta 400 MB).
2. Para un paso: edita el paso y agrégalo en *Modelos y animaciones del visor*.
   Un paso puede tener varios; se ordenan con las flechas.
3. Para un instrumento: edita el instrumento y elige su *Modelo 3D*. Un mismo instrumento
   se asigna a muchos pasos sin volver a cargar el archivo.
4. *Reemplazar* cambia el archivo en todos sus usos del borrador.

El visor reproduce las animaciones que ya vienen dentro de un GLB (reproducir, pausar, reiniciar,
avanzar, retroceder y velocidad), y permite girar, acercar, cambiar de vista y ocultar piezas.
Los STL no guardan animación; solo se pueden examinar.

Al pasar el cursor sobre una pieza aparece su nombre, y al hacer clic queda fijo. Ese nombre es el
que tiene la pieza dentro del archivo 3D (`Hoja_helicoidal` se muestra como «Hoja helicoidal»),
así que para cambiarlo hay que renombrarla en el programa de modelado y exportar de nuevo.

Recomendación: los STL de 50 a 120 MB tardan en abrir. Conviene reducirlos o pasarlos a GLB comprimido.

## Ilustraciones

Las imágenes de las etapas 1 a 4 son escenas 3D: `web/ilustraciones3d/escenas.js` las arma (paciente,
mesa, arco en C y el fémur del modelo del proyecto) y `ilustraciones/generar3d.py` las fotografía con
Edge mientras el servidor está abierto. La versión anterior, plana, quedó en `ilustraciones/esquemas-2d`.

Las imágenes 1.1 y 1.2 se hicieron con IA (Kie.ai). Las originales sin texto están en `ilustraciones/ia`,
y `ilustraciones/componer.py` les pone los textos encima. Las versiones 3D de esas dos quedaron en
`ilustraciones/escenas-3d`. Una imagen se agrega o se quita
en **Modo edición**, en *Imágenes de este paso*, y se ve a la derecha si el paso no tiene animación propia.

## Estructura

```
server.py            Servidor HTTP: rutas, sesiones, archivos y cabeceras de seguridad
app/db.py            Persistencia: esquema de SQLite
app/auth.py          Autenticación: contraseñas, sesiones y límite de intentos
app/content.py       Contenido: pasos, instrumental, animaciones, borrador y publicación
app/assets.py        Archivos: carga, reutilización, reemplazo y eliminación
app/api.py           API y permisos por ruta
app/seed.py          Contenido de ejemplo y cuentas iniciales
web/css/tokens.css   Identidad visual: colores, tipografía y medidas de la marca
web/js/core/         Navegación, estado y cliente de la API
web/js/components/   Barra superior y visor 3D (viewer3d.js es el motor)
web/js/views/        El instructivo (instructivo.js) e ingreso al administrador
web/js/admin/        Pantallas del administrador
web/vendor/three/    Three.js 0.160 (licencia MIT), incluido para funcionar sin conexión al CDN
tests/               Pruebas de la API: python -m unittest discover -s tests
data/                Base de datos y archivos subidos (se crea sola; haz copia de esta carpeta)
```

## Versión pública (solo para ver)

`python exportar.py` crea la carpeta `publicar/` con la última versión publicada: textos, imágenes y
modelos, sin cuentas ni borradores. Esa carpeta se sube a Vercel o a Netlify. La edición sigue en el
computador: al cambiar algo, se publica en el modo edición, se vuelve a correr `exportar.py` y se sube de nuevo.

## Antes de publicarla en internet

Esta versión está pensada para uso local. Para un servidor real hace falta HTTPS
(con un proxy delante y la opción `--https`), copias de seguridad de `data/` y definir
si el instructivo debe exigir inicio de sesión: hoy se puede consultar sin cuenta.
