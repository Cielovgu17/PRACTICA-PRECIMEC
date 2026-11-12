# Animaciones del instructivo

Archivos GLB que usa el instructivo, tal como se publican. Los originales de Blender no se modifican;
estas son copias con las correcciones aplicadas por las herramientas de `ilustraciones/`:

- `femur_limpio.py`: fémur con superficie continua y diáfisis con contornos suaves.
- `ajustar_animaciones.py`: el instrumental conserva el recorrido que se animó en Blender; es el hueso el que se
  acomoda a él (grupo Anatomia de cada escena): la punta del trocánter mayor (su parte más alta) queda en el punto
  de entrada, el hueso se agranda 5 % y se gira ~6,7° para que el canal siga al pin guía. El pin llega a 250 mm
  desde la superficie (1 cm más que el clavo de Φ9,4 × 240 mm), el protector se apoya sobre el hueso y la broca
  canulada de Φ16,5 mm baja hasta que su tope toca la camisa. `femur_limpio.py` tapa el orificio que traía el
  modelo en el lugar anterior.

| Archivo | Paso |
|---|---|
| apertura_canal_medular_KTO-PFNA_completo - entrada en la punta.glb | 3.1 Entregar el abridor canulado |
| Animación Fresado del canal medular Sub 2 - entrada en la punta.glb | 3.2 Montar y entregar el pin guía roscado |
| Animación Fresado del canal medular Sub 3 (retiro trocar) - entrada en la punta.glb | 3.3 Retirar el mango y entregar el protector de tejidos |
| paso4_broca_canulada_KTO-PFNA - entrada en la punta.glb | 3.4 Montar y entregar la broca canulada para el fresado proximal |
| paso10_montaje_varilla_refuerzo_KTO-PFNA.glb | 6.1 Instalar y fijar el brazo de soporte |
| paso11_conjunto_guias_KTO-PFNA.glb | 6.2 Armar y pasar el conjunto de guías (el trocar se queda; se aprieta la tuerca) |
| paso12_pin_guia_roscado_KTO-PFNA - centrado en la cabeza.glb | 6.3 Retirar el trocar, montar el pin guía roscado y asistir la perforación |
| Animacion_Insercion_Hoja_PFNA.glb | 6.8 Entregar el martillo para impactar la hoja |

Bloqueo proximal: para que el pin guía vaya por el centro de la cabeza sin que las piezas se atraviesen, se conserva el ángulo del instrumental (CCD 130°) y `ajustar_animaciones.py` baja 25 mm el orificio de la hoja en el clavo (la parte proximal gruesa queda más larga; se aplica en todos los pasos desde el 5.1) y alarga 25 mm el tramo recto del brazo de soporte. Las guías, el perforador y el pin bajan lo mismo, sin girar.

`aligerar.py` promedia los puntos de cada pieza completa (no por partes) para que no queden rendijas entre las partes en que Blender divide las piezas grandes.

Desde el paso 5.5 no se muestran las marcas del hueso trabajado en la etapa del canal medular (hueco del abridor, túnel de la broca de Φ16,5 y canal escariado): `ilustraciones/quitar_marcas.py` se las quita a cada archivo de esos pasos después de prepararlo.
