# Fragmento de core/retiro_programado.py :: proyectar_rp_dinamico_cai
# Bucle principal de la recursión año a año.
    for indice_anio in range(max_anios):
        if cai_actual <= 0:
            break

        datos_anio = replace(datos, fecha_valoracion=fecha_valoracion_actual.date())
        resultado_metodo, _, _, _ = resolver_mesada_rp(datos_anio, cai_actual, params, mesada_referencia_rv=mesada_referencia_rv)
        mesada_calculada = resultado_metodo.valor
        if not resultado_metodo.convergio:
            # Cuando no hay una raiz real en el rango de busqueda [SMLV,
            # SMLV*25], cada metodo numerico "degenera" hacia un limite
            # distinto (biseccion tiende al limite superior si no logra
            # acotar una raiz real; secante/newton acotados tienden al
            # limite inferior) -- ninguno de los 2 valores es una
            # respuesta actuarial real. Se normaliza siempre al SMLV
            # PROYECTADO a este año (misma formula de crecimiento que usa
            # el motor de reserva: SMLV*(1+IPC+deslizamiento)^n -- el
            # salario minimo legal tambien crece con el tiempo, no se
            # queda fijo en el valor de hoy), para que el resultado no
            # dependa de que metodo de iteracion este configurado, y para
            # que la mesada de las cedulas "pegadas al SMLV" seguga
            # reflejando el crecimiento real del salario minimo en vez de
            # quedar congelada en pesos nominales de hoy.
            mesada_calculada = params.smlv * factor_crecimiento_rp(indice_anio, params, datos.mesada_actual_rp)
        anio_actual = fecha_valoracion_actual.year
        es_primer_anio = mesada_anterior is None
        # El fondo no tiene una solucion actuarial valida en este año --
        # sea porque quedo pegado al SMLV (limite inferior de la
        # busqueda), sea porque el metodo configurado no convergio del
        # todo (Convergio=False). Esto ultimo importa porque un metodo que
        # no converge puede "degenerar" hacia CUALQUIERA de los 2 limites
        # de busqueda segun el algoritmo (biseccion tiende a degenerar
        # hacia el limite superior si no logra acotar una raiz real,
        # mientras que secante/newton acotados tienden a degenerar hacia
        # el limite inferior) -- ninguno de los 2 valores es una respuesta
        # actuarial real en ese caso, asi que NO hay que forzar el techo
        # comercial (RP cerca de RV) sobre un numero que no significa nada.
        pegado_al_smlv = mesada_calculada <= params.smlv * (1 + 1e-9) or not resultado_metodo.convergio

        piso_aplicado = False
        if not es_primer_anio and mesada_anterior > params.smlv * (1 + 1e-9) and not pegado_al_smlv:
            # Solo se exige el crecimiento minimo si HABIA margen real por
            # encima del SMLV tanto el año anterior como este año -- si
            # cualquiera de los 2 esta pegado al piso legal, forzar
            # crecimiento seria pedirle al fondo plata que no tiene (y
            # podria hasta empujar a RP por encima de RV, si RV tambien
            # viene bajando). El crecimiento minimo exigido es el
            # crecimiento INCREMENTAL de este año vs el año anterior, con
            # el mismo esquema de 3 tramos de IPC que usa Renta Vitalicia.
            factor_incremental = factor_crecimiento_rp(indice_anio, params, datos.mesada_actual_rp) / factor_crecimiento_rp(indice_anio - 1, params, datos.mesada_actual_rp)
            mesada_piso = mesada_anterior * factor_incremental
            if mesada_piso > mesada_calculada:
                piso_aplicado = True
            mesada_anio = max(mesada_calculada, mesada_piso)
        else:
            mesada_anio = mesada_calculada

        techo_aplicado = False
        smlv_proyectado_este_anio = params.smlv * factor_crecimiento_rp(indice_anio, params, datos.mesada_actual_rp)
        # La condicion comercial "Renta Vitalicia > Retiro Programado" es
        # OPCIONAL (peticion del usuario 2026-08-18): solo se aplica si
        # params.aplicar_condicion_rv_mayor es True, y en ese caso desde el
        # año params.anio_inicio_condicion_rv (1-indexado; por defecto 3).
        # Desactivada (default), la mesada de RP sale UNICAMENTE de su
        # propia dinamica actuarial (piso de crecimiento, SMLV proyectado)
        # mas el riesgo de mercado del crecimiento de la CAI -- que es lo
        # que, de forma organica, la lleva a quedar por debajo de RV.
        aplica_condicion_rv = (
            params.aplicar_condicion_rv_mayor
            and indice_anio >= max(params.anio_inicio_condicion_rv - 1, 0)
        )
        if aplica_condicion_rv and mesada_rv_por_anio and anio_actual in mesada_rv_por_anio:
            rv_anio = mesada_rv_por_anio[anio_actual]
            # Rampa lineal: margen chico apenas empieza a aplicar (año 3),
            # creciendo hasta MARGEN_RP_FINAL en el ultimo año del
            # horizonte proyectado (la brecha se va abriendo con el tiempo).
            if max_anios > 1:
                fraccion = indice_anio / (max_anios - 1)
            else:
                fraccion = 0.0
            margen_este_anio = MARGEN_RP_ANIO1 + (MARGEN_RP_FINAL - MARGEN_RP_ANIO1) * fraccion
            # El SMLV PROYECTADO es un piso legal, siempre tiene prioridad
            # sobre el techo comercial (RP<RV): si el (1-margen) de RV cae
            # por debajo del SMLV proyectado de ese año (puede pasar: el
            # SMLV crece con IPC+deslizamiento, mas rapido que el
            # esquema de IPC que usa RV en la mayoria de los casos), el
            # techo efectivo es el SMLV proyectado, no ese valor menor --
            # por ley, nunca se puede pagar menos de un SMLV, ni siquiera
            # para mantener la garantia comercial RV>RP.
            techo = max(rv_anio * (1 - margen_este_anio), smlv_proyectado_este_anio)

            if mesada_anio > techo:
                techo_aplicado = True
                mesada_anio = techo
            elif mesada_anio < smlv_proyectado_este_anio:
                # Salvaguarda: el SMLV proyectado nunca se viola, ni
                # aunque el piso de crecimiento/techo hayan dado algo
                # menor por algun caso limite.
                mesada_anio = smlv_proyectado_este_anio
        elif mesada_anio < smlv_proyectado_este_anio:
            # Fuera de la ventana de la condicion RV>RP (años 1-2), el
            # SMLV proyectado sigue siendo un piso legal que nunca se viola.
            mesada_anio = smlv_proyectado_este_anio

        if es_primer_anio and mesada_rv_por_anio and anio_actual in mesada_rv_por_anio:
            # El año 1 de RP arranca EXACTAMENTE en la misma mesada que
            # Renta Vitalicia (peticion del usuario 2026-08-20) -- no una
            # aproximacion, no un margen: el valor exacto de RV ese año.
            # Esto es INCONDICIONAL (no depende de si la condicion
            # comercial "RV>RP" esta activada, esa condicion es sobre los
            # años SIGUIENTES del horizonte, no sobre el arranque) y tiene
            # la ULTIMA palabra sobre cualquier ajuste anterior (piso,
            # techo comercial). El SMLV proyectado se mantiene como piso
            # legal absoluto, por si RV mismo estuviera, en un caso
            # extremo, por debajo del SMLV.
            rv_anio1 = mesada_rv_por_anio[anio_actual]
            mesada_exacta_esperada = max(rv_anio1, smlv_proyectado_este_anio)
            if mesada_anio != mesada_exacta_esperada:
                techo_aplicado = True
            mesada_anio = mesada_exacta_esperada

        # LIMITE DE CAIDA ANUAL (peticion del usuario 2026-08-21): la
        # mesada de RP no puede caer mas de params.caida_maxima_anual_rp
        # (50% por defecto) respecto a la del año anterior. Se aplica al
        # FINAL, despues de todos los demas ajustes (piso de crecimiento,
        # techo comercial, SMLV proyectado, arranque en RV), porque es el
        # ultimo filtro sobre lo que efectivamente se paga.
        #
        # Este ajuste solo puede SUBIR la mesada, nunca bajarla, asi que no
        # entra en conflicto con el piso legal del SMLV proyectado. Lo que
        # se pague de mas si sale del saldo real de la CAI (ver el descuento
        # mas abajo), asi que el fondo se agota antes -- exactamente como
        # pasa con el piso de crecimiento.
        caida_limitada = False
        if not es_primer_anio and mesada_anterior is not None:
            piso_caida = mesada_anterior * (1 - params.caida_maxima_anual_rp)
            if mesada_anio < piso_caida:
                caida_limitada = True
                mesada_anio = piso_caida

        tasa_crecimiento_este_anio = float(tasas_crecimiento_sorteadas[indice_anio])

        filas.append({
            "Anio": anio_actual,
            "Mesada_Pensional_proyectada": mesada_anio,
            "Mesada_sin_piso": mesada_calculada,
            "Saldo_CAI_inicio_anio": cai_actual,
            "Convergio": resultado_metodo.convergio,
            "Piso_aplicado": piso_aplicado,
            "Techo_aplicado": techo_aplicado,
            "Caida_limitada": caida_limitada,
            "Tasa_crecimiento_CAI_este_anio": tasa_crecimiento_este_anio,
        })

        if not resultado_metodo.convergio:
            # El calculo actuarial dice que el saldo actual ya no alcanza
            # para garantizar ni el SMLV -- la CAI no tiene capital
            # suficiente para sostener un SMLV. Se detiene la proyeccion
            # AQUI (esta es la ultima fila que se genera); no se sigue
            # "estimando" años que el fondo ya no puede sostener.
            break

        if detener_al_cruzar_rv and mesada_rv_por_anio and anio_actual in mesada_rv_por_anio:
            # Horizonte DINAMICO (peticion del usuario 2026-08-18): la
            # proyeccion se extiende año a año hasta que la mesada de
            # Retiro Programado quede por debajo de la de Renta Vitalicia
            # -- ese es el dato que interesa mostrar. Una vez ocurre, este
            # año queda como el ultimo de la serie. Si nunca ocurre, la
            # proyeccion corre hasta max_anios (el tope duro).
            if mesada_anio < mesada_rv_por_anio[anio_actual]:
                break

        mesada_anterior = mesada_anio

        total_pagado_anio = mesada_anio * datos.n_mesadas
        cai_actual = (cai_actual - total_pagado_anio) * (1 + tasa_crecimiento_este_anio)

        fecha_valoracion_actual = fecha_valoracion_actual + pd.DateOffset(years=1)
