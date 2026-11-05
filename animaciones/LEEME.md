# Animaciones del instructivo

Archivos GLB que usa el instructivo, tal como se publican. Los originales de Blender no se modifican;
estas son copias con las correcciones aplicadas por las herramientas de `ilustraciones/`:

- `femur_limpio.py`: fémur con superficie continua y diáfisis con contornos suaves.
- `ajustar_animaciones.py`: en los pasos 3.2, 3.3 y 3.4 el pin guía, el protector, la broca y el perforador se giran
  ~3° alrededor del punto de entrada para seguir el eje del canal medular. El pin llega a 250 mm desde la entrada
  (1 cm más que el clavo de Φ9,4 × 240 mm), el protector de tejidos queda apoyado sobre el hueso y la broca
  canulada de Φ16,5 mm baja hasta que su tope toca la camisa del protector.
- `reubicar_femur.py`: en los pasos 3.1 a 3.4 el fémur es 12 % más grande y está reubicado alrededor del instrumental.
  El punto de entrada queda en el vértice del trocánter mayor, en la unión del tercio anterior con los dos
  tercios posteriores, y el eje del pin pasa por el centro del canal medular. Bajo el trocánter la pared se
  ensancha para que la broca de Φ16,5 mm y el clavo queden dentro del hueso: alrededor del eje quedan al
  menos 11 mm de hueso en todo el recorrido del pin. La guía de tercios del paso 3.1 se mueve con el hueso.
  El instrumental y sus movimientos no cambian.

Para actualizar el instructivo: en el modo edición, *Modelos y archivos*, usa **Reemplazar** en cada uno de los
cuatro archivos de los pasos 3.1 a 3.4 con la versión de esta carpeta y luego **Publicar**.

| Archivo | Paso |
|---|---|
| apertura_canal_medular_KTO-PFNA_completo - femur continuo.glb | 3.1 Entregar el abridor canulado |
| Animación Fresado del canal medular Sub 2 - alineado al canal.glb | 3.2 Montar y entregar el pin guía roscado |
| Animación Fresado del canal medular Sub 3 (retiro trocar) - alineado al canal.glb | 3.3 Retirar el mango y entregar el protector de tejidos |
| paso4_broca_canulada_KTO-PFNA - alineado al canal.glb | 3.4 Montar y entregar la broca canulada para el fresado proximal |
| Animacion_Insercion_Hoja_PFNA.glb | 6.8 Entregar el martillo para impactar la hoja |
