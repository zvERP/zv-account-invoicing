"""Cálculo puro (sin dependencias de Odoo) de los intereses de demora.

Convenciones:
- Un día de demora ``x`` pertenece al intervalo (fecha_vencimiento, fecha_fin].
  Los días de demora son ``fecha_fin - fecha_vencimiento``.
- El importe pendiente en el día ``x`` es el principal menos los cobros con
  fecha anterior a ``x``: el día en el que se cobra todavía devenga intereses.
- Interés simple: base * tipo / 100 * días / 365.
- La base es el importe total de la factura, IVA incluido (doctrina del
  Tribunal Supremo, p. ej. STS de 8 de marzo de 2023).
"""
from datetime import timedelta

YEAR_DAYS = 365
# Ley 3/2004, art. 4.1: plazo de pago legal supletorio y máximo pactable.
DEFAULT_PAYMENT_DAYS = 30
MAX_PAYMENT_DAYS = 60


def legal_due_date(invoice_date, invoice_date_due):
    """Último día de pago sin demora (art. 4 Ley 3/2004).

    El vencimiento pactado (30 días si no consta), con un máximo de 60 días
    desde la fecha de la factura.
    """
    if not invoice_date:
        return invoice_date_due or None
    due = invoice_date_due or invoice_date + timedelta(days=DEFAULT_PAYMENT_DAYS)
    return min(due, invoice_date + timedelta(days=MAX_PAYMENT_DAYS))


def compute_late_interest(due_date, end_date, principal, payments, rate):
    """Calcula los tramos de intereses de demora.

    :param due_date: fecha de vencimiento (último día sin demora)
    :param end_date: fecha de cobro total, o la fecha de cálculo si sigue pendiente
    :param principal: importe adeudado (total de la factura, IVA incluido)
    :param payments: lista de tuplas ``(fecha, importe)`` de cobros/compensaciones
    :param rate: tipo de interés nominal anual, en porcentaje
    :return: lista de dicts con date_from, date_to, days, base, rate e interest;
        un tramo por cada cambio del importe pendiente
    """
    if not due_date or not end_date or end_date <= due_date:
        return []

    breakpoints = sorted(
        {due_date, end_date} | {d for d, _a in payments if due_date < d < end_date}
    )
    segments = []
    for d1, d2 in zip(breakpoints, breakpoints[1:]):
        first_day = d1 + timedelta(days=1)
        paid = sum(amount for pay_date, amount in payments if pay_date < first_day)
        base = max(principal - paid, 0.0)
        if base <= 0:
            continue
        days = (d2 - d1).days
        segments.append({
            "date_from": first_day,
            "date_to": d2,
            "days": days,
            "base": base,
            "rate": rate,
            "interest": base * rate / 100.0 * days / YEAR_DAYS,
        })
    return segments
