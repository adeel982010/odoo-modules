# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime

class CustomerWizardLine(models.TransientModel):
    _name = 'customer.wizard.line'
    
    name = fields.Char('Name')
    partner_id = fields.Many2one('res.partner','Customer')
    email = fields.Char('Email')
    phone = fields.Char('Phone')
    wizard_id = fields.Many2one('customer.wizard','Wizard')
    
class CustomerWizard(models.TransientModel):
    _name = 'customer.wizard'
    
    customer_ids = fields.One2many('customer.wizard.line','wizard_id', string='Customers')
    
    @api.model
    def default_get(self,fields):
        res = super(CustomerWizard,self).default_get(fields)
                
        qry = """SELECT p.id
FROM res_partner p
    LEFT JOIN crm_lead lead ON lead.partner_id = p.id
    LEFT JOIN calendar_event_res_partner_rel ce ON ce.res_partner_id = p.id
    LEFT JOIN crm_phonecall call ON call.partner_id = p.id
    LEFT JOIN account_invoice inv ON inv.partner_id = p.id
    LEFT JOIN sale_order o ON o.partner_id = p.id
    LEFT JOIN account_move move ON move.partner_id = p.id
    LEFT JOIN account_move_line line ON line.partner_id = p.id
    LEFT JOIN project_task task ON task.partner_id = p.id
WHERE
    lead.partner_id is null and 
    ce.res_partner_id is null and
    call.partner_id is null and
    inv.partner_id is null and
    o.partner_id is null and
    move.partner_id is null and
    line.partner_id is null and
    task.partner_id is null and 
    p.active and
    p.customer and
    p.id not in (select partner_id from res_users)
    """
        partner_obj = self.env['res.partner']
        if hasattr(partner_obj, 'newsletter_sendy'):
            qry += " and not p.newsletter_sendy"   
        self._cr.execute(qry)
        data = self._cr.fetchall()
        customer_ids = [p[0] for p in data]
        lines = []
        for customer in partner_obj.browse(customer_ids):
            lines.append((0,0,{'partner_id': customer.id, 'email': customer.email, 'phone': customer.phone, 'name': customer.name}))
        res.update({'customer_ids':lines})
        return res
    
    
    @api.multi
    def action_remove_customer(self):
        current_date = datetime.now()
        log_obj = self.env['removed.record.log']
        user_id = self.env.user.id
        
        customer_ids = self.customer_ids.mapped('partner_id').ids
        partner_obj = self.env['res.partner']
        
        for partner_id in customer_ids:
            #Browse one record only, because if partner linked to some record and raise exception when deleting record, than system will just rollback that transaction.
            self._cr.execute('SAVEPOINT remove_partner')
            line = partner_obj.browse(partner_id)
            record_name = line.name
            record_id = line.id
            try:
                line.unlink()
            except Exception as e:
                self._cr.execute('ROLLBACK TO SAVEPOINT remove_partner')
                self._cr.execute('SAVEPOINT remove_partner')
                line = partner_obj.browse(partner_id)
                line.write({'active':False})
                
            log_obj.create({
                    'name' : record_name,
                    'date' : current_date,
                    'res_model': 'res.partner',
                    'res_id': record_id,
                    'user_id' : user_id,
                    })
            self._cr.execute('RELEASE SAVEPOINT remove_partner')
        return
    
    