# Fragmento de core/motor.py :: calcular_reserva(...)
# Se ejecuta solo cuando se invoca con calcular_derivada=True.
    # --- Derivadas laterales exactas de la Reserva Matematica (opcional) ---
    #
    # VP(M) es lineal por tramos en M. Sus dos sumandos dependientes de M son
    #
    #   renta:   max(M*tau_t, S_t)            (maximo -> convexo)
    #   auxilio: med(5*S_t, M*tau_t, 10*S_t)  (clamp  -> NO convexo)
    #
    # con tau_t = tasa_aplicar[t] y S_t = salario_minimo_proyectado[t]. Las
    # derivadas laterales se obtienen sumando tau_t sobre los terminos
    # ACTIVOS, con el criterio de desigualdad estricta/no estricta que
    # corresponde a cada lado. El par (izq, der) es el B-subdiferencial de
    # Qi; su envolvente convexa es el subdiferencial de Clarke.
    derivada_rm_der = derivada_rm_izq = 0.0
    derivada_rm_rp_der = derivada_rm_rp_izq = 0.0
    n_activos_renta = n_activos_auf = 0
    if calcular_derivada:
        # HALLAZGO DOCUMENTADO EN LA TESIS (cap. de estructura funcional):
        # el motor elige `tasa_aplicar` por una distincion de casos
        # (M == SMLV -> factor con deslizamiento; M != SMLV -> factor IPC).
        # El VALOR de VP es continuo en M = SMLV (el piso del salario minimo
        # absorbe la diferencia), pero la FORMULA de la derivada no lo es:
        # evaluada literalmente en M = SMLV devolveria la pendiente de la
        # rama con deslizamiento, cuando la derivada lateral derecha
        # verdadera (limite cuando eps -> 0+) se calcula sobre la rama IPC.
        # Se usa la rama IPC para la derivada en ese punto, que es la que
        # corresponde al limite; la derivada por izquierda es 0 porque VP
        # es constante en [0, SMLV].
        tasa_derivada = factor_ipc if datos.mesada_actual == datos.smlv else tasa_aplicar
        m_tau = datos.mesada_actual * tasa_derivada
        peso_renta = tasa_derivada * vigencia_general * numero_mesadas * np.nan_to_num(npx_lead, nan=0.0) * np.nan_to_num(descuento_tecnico_lead, nan=0.0)

        activo_renta_der = m_tau >= salario_minimo_proyectado
        activo_renta_izq = m_tau > salario_minimo_proyectado
        d_rab_der = float(np.sum(np.where(activo_renta_der, peso_renta, 0.0)))
        d_rab_izq = float(np.sum(np.where(activo_renta_izq, peso_renta, 0.0)))
        n_activos_renta = int(np.count_nonzero(activo_renta_der & (vigencia_general > 0)))

        d_auf_der = d_auf_izq = 0.0
        if datos.causante.estado != config.ESTADO_MUERTO and tabla_causante is not None:
            peso_auf = tasa_derivada * vigencia_general * np.nan_to_num(qx_t_causante, nan=0.0) * np.nan_to_num(npx_causante, nan=0.0) * np.nan_to_num(descuento_tecnico_lead, nan=0.0)
            banda_der = (m_tau >= 5 * salario_minimo_proyectado) & (m_tau < 10 * salario_minimo_proyectado)
            banda_izq = (m_tau > 5 * salario_minimo_proyectado) & (m_tau <= 10 * salario_minimo_proyectado)
            d_auf_der = float(np.sum(np.where(banda_der, peso_auf, 0.0)))
            d_auf_izq = float(np.sum(np.where(banda_izq, peso_auf, 0.0)))
            n_activos_auf = int(np.count_nonzero(banda_der & (vigencia_general > 0)))

        d_base_der = (1 + params.porcentaje_reserva_cambio_grupo) * d_rab_der + d_auf_der
        d_base_izq = (1 + params.porcentaje_reserva_cambio_grupo) * d_rab_izq + d_auf_izq

        escala_rm = 1.0 / (1 - params.porcentaje_recargo_gastos_reserva)
        derivada_rm_der = d_base_der * escala_rm
        derivada_rm_izq = d_base_izq * escala_rm

        if datos.porcentaje_sobrecosto_mortalidad is not None or datos.porcentaje_gastos_rp is not None:
            pct_s = datos.porcentaje_sobrecosto_mortalidad or 0.0
            pct_g = datos.porcentaje_gastos_rp or 0.0
            escala_rp = 1.0 / (1 - pct_s) + 1.0 / (1 - pct_g) - 1.0
            derivada_rm_rp_der = d_base_der * escala_rp
            derivada_rm_rp_izq = d_base_izq * escala_rp
