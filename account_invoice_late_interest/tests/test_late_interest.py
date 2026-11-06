from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..models.late_interest_calc import compute_late_interest, legal_due_date


@tagged("post_install", "-at_install")
class TestLateInterestCalc(AccountTestInvoicingCommon):
    def test_single_period(self):
        segs = compute_late_interest(date(2025, 2, 1), date(2025, 3, 3), 1000.0, [], 10.40)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["days"], 30)
        self.assertEqual(segs[0]["date_from"], date(2025, 2, 2))
        self.assertAlmostEqual(segs[0]["interest"], 1000 * 0.1040 * 30 / 365)

    def test_partial_payment(self):
        segs = compute_late_interest(
            date(2025, 6, 20), date(2025, 7, 20), 1000.0, [(date(2025, 7, 10), 400.0)], 10.0
        )
        self.assertEqual([s["days"] for s in segs], [20, 10])
        self.assertEqual([s["base"] for s in segs], [1000.0, 600.0])

    def test_no_interest_when_paid_on_time(self):
        self.assertEqual(compute_late_interest(date(2025, 2, 1), date(2025, 1, 30), 1000.0, [], 10.0), [])

    def test_legal_due_date(self):
        # Vencimiento pactado dentro del máximo legal
        self.assertEqual(legal_due_date(date(2025, 1, 1), date(2025, 1, 31)), date(2025, 1, 31))
        # Pacto superior a 60 días: se limita a 60 días (art. 4.1 Ley 3/2004)
        self.assertEqual(legal_due_date(date(2025, 1, 1), date(2025, 4, 1)), date(2025, 3, 2))
        # Sin vencimiento: 30 días
        self.assertEqual(legal_due_date(date(2025, 1, 1), None), date(2025, 1, 31))


@tagged("post_install", "-at_install")
class TestLateInterestInvoice(AccountTestInvoicingCommon):
    def setUp(self):
        super().setUp()
        self.tag = self.env["res.partner.category"].create({"name": "Reclamar intereses"})
        Config = self.env["account.late.interest.config"]
        self.config = Config._get_for_company(self.env.company) or Config.create({})
        self.config.write({
            "partner_category_ids": [(6, 0, self.tag.ids)],
            "rate": 10.0,
            "representative_name": "D. Nombre de prueba",
            "representative_vat": "00000000T",
            "notification_address": "Rúa de Proba 1, 15001 A Coruña",
        })
        self.partner_a.category_id = [(4, self.tag.id)]

    def _paid_invoice(self, partner, payment_date):
        invoice = self.init_invoice(
            "out_invoice", partner=partner, invoice_date="2025-01-01", amounts=[1000.0],
            taxes=self.tax_sale_a, post=True,
        )
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"payment_date": payment_date})._create_payments()
        return invoice

    def test_defaults(self):
        config = self.env["account.late.interest.config"].new({})
        self.assertEqual(config.rate, 10.40)
        self.assertEqual(config.compensation, 40.0)

    def test_untagged_partner_has_no_interest(self):
        invoice = self._paid_invoice(self.partner_b, "2025-03-15")
        self.assertFalse(invoice.late_interest_enabled)
        self.assertFalse(invoice.late_interest_applicable)
        self.assertEqual(invoice.late_interest_amount, 0.0)

    def test_invoice_paid_late(self):
        invoice = self._paid_invoice(self.partner_a, "2025-02-15")
        self.assertTrue(invoice.late_interest_enabled)
        self.assertTrue(invoice.late_interest_applicable)
        self.assertTrue(invoice.late_interest_fully_paid)
        self.assertEqual(invoice.late_interest_due_date, invoice.invoice_date_due)
        days = (date(2025, 2, 15) - invoice.invoice_date_due).days
        self.assertEqual(invoice.late_interest_days, days)
        # Base: total de la factura, IVA incluido
        self.assertEqual(invoice.late_interest_base, invoice.amount_total)
        self.assertAlmostEqual(
            invoice.late_interest_amount, round(invoice.amount_total * 0.10 * days / 365, 2)
        )
        self.assertEqual(invoice.late_interest_compensation, 40.0)

    def test_invoice_claim(self):
        invoice = self._paid_invoice(self.partner_a, "2025-04-01")
        invoice.late_interest_due_date_manual = date(2025, 3, 2)
        self.assertEqual(invoice.late_interest_days, 30)

        report = self.env.ref("account_invoice_late_interest.action_report_late_interest_claim")
        # En el menú Imprimir de las facturas
        self.assertEqual(report.binding_model_id.model, "account.move")
        self.assertEqual(report.binding_type, "report")

        # Igual que el cliente web: solo los ids, sin datos adicionales
        html, _ = self.env["ir.actions.report"]._render_qweb_html(report.report_name, invoice.ids)
        self.assertIn(b"QUINTO", html)
        self.assertIn(invoice.company_id.name.upper().encode(), html)
        self.assertIn("D. Nombre de prueba".encode(), html)
        self.assertIn("RÚA DE PROBA 1".encode(), html)

    def test_claim_requires_interest(self):
        invoice = self._paid_invoice(self.partner_b, "2025-04-01")
        report = self.env.ref("account_invoice_late_interest.action_report_late_interest_claim")
        with self.assertRaises(UserError):
            self.env["ir.actions.report"]._render_qweb_html(report.report_name, invoice.ids)
