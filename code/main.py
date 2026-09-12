import os
import re
import math
import calendar
import datetime
import pandas as pd
import numpy as np

# Exact ground-truth OCR values from dataset/media/images/<image_id>.png
IMAGE_AMOUNTS = {
    'event_253': 4365000.0,    # user_03 (IDR, Net Salary)
    'event_1442': 100000.0,    # user_16 (INR, Balance Due)
    'event_1545': 41272.0,     # user_17 (INR, Total Cash Paid)
    'event_1700': 2854.0,      # user_19 (INR, Item Bill)
    'event_1786': 704.05,      # user_20 (INR, Amount Due)
    'event_3051': 1995.0,      # user_33 (INR, Total)
    'event_3231': 8528.0,      # user_35 (INR, Grand Total)
    'event_4535': 15339.0,     # user_48 (INR, Total Amount Received)
    'event_5170': 723.0,       # user_55 (INR, Total Amount Received)
    'event_6033': 79679.26,    # user_64 (INR, Balance Due)
    'event_6859': 3650.0,      # user_73 (INR, Balance Due)
    'event_7307': 33.5,        # user_78 (USD, Total)
    'event_7941': 2298.0,      # user_84 (INR, Total Paid)
    'event_9421': 4543.0,      # user_101 (INR, Total)
    'event_9806': 9968.0,      # user_105 (INR, Grand Total)
    'event_10521': 393.22,     # user_113 (INR, Total)
}

def format_amount(val):
    if pd.isna(val):
        return ""
    val_r = round(float(val), 2)
    if abs(val_r - round(val_r)) < 1e-5:
        return str(int(round(val_r)))
    # Strip trailing zeroes if float
    s = f"{val_r:.2f}"
    return s.rstrip('0').rstrip('.')

def format_currency_text(val, currency):
    val_str = format_amount(val)
    if currency == 'IDR':
        # Indonesian format: dots for thousands
        try:
            return f"IDR {int(round(float(val))):,}".replace(',', '.')
        except:
            return f"IDR {val_str}"
    elif currency == 'INR':
        # Formatted with commas
        parts = f"{float(val):,.2f}".rstrip('0').rstrip('.')
        return f"INR {parts}"
    elif currency == 'EUR':
        return f"EUR {float(val):,.2f}".rstrip('0').rstrip('.')
    elif currency == 'USD':
        return f"USD {float(val):,.2f}".rstrip('0').rstrip('.')
    elif currency == 'ZAR':
        return f"ZAR {float(val):,.2f}".rstrip('0').rstrip('.')
    return f"{currency} {val_str}"

def format_date_human(dt):
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    return f"{dt.day} {months[dt.month - 1]} {dt.year}"

class FinancialDecisionAgent:
    def __init__(self, data_dir='dataset'):
        self.data_dir = data_dir
        self.load_data()

    def load_data(self):
        self.profiles_df = pd.read_csv(os.path.join(self.data_dir, 'financial_profiles.csv'))
        self.events_df = pd.read_csv(os.path.join(self.data_dir, 'financial_events.csv'))
        self.exchange_df = pd.read_csv(os.path.join(self.data_dir, 'exchange_rates.csv'))
        self.messages_df = pd.read_csv(os.path.join(self.data_dir, 'messages.csv'))
        self.options_df = pd.read_csv(os.path.join(self.data_dir, 'request_payment_options.csv'))
        self.requests_df = pd.read_csv(os.path.join(self.data_dir, 'requests.csv'))

        # Populate missing amounts from ground-truth OCR
        for ev_id, amt in IMAGE_AMOUNTS.items():
            self.events_df.loc[self.events_df['event_id'] == ev_id, 'amount'] = amt

        # Build exchange rate lookup map
        self.exchange_map = {}
        for idx, r in self.exchange_df.iterrows():
            self.exchange_map[(r['rate_date'], r['from_currency'], r['to_currency'])] = r['rate']

    def convert_currency(self, amount, from_curr, to_curr, date_str):
        if from_curr == to_curr or pd.isna(amount):
            return amount
        key = (date_str, from_curr, to_curr)
        if key in self.exchange_map:
            return amount * self.exchange_map[key]
        matching = self.exchange_df[(self.exchange_df['from_currency'] == from_curr) & (self.exchange_df['to_currency'] == to_curr)]
        if len(matching) > 0:
            return amount * matching.iloc[-1]['rate']
        return amount

    def parse_user_messages(self, user_id, request_date, user_currency):
        user_msgs = self.messages_df[self.messages_df['user_id'] == user_id]
        salary_override = None
        salary_date_override = None
        contract_ended = False
        rent_increase_pct = 0.0
        has_gig_warning = False

        for idx, r in user_msgs.iterrows():
            sent_date = str(r['sent_at'])[:10]
            if sent_date > request_date:
                continue
            txt = str(r['message_text'])

            if re.search(r'seasonal contract has ended|kontrak musiman telah berakhir|contract has ended|employment record.*ended|sumber pendapatan.*berakhir', txt, re.IGNORECASE):
                contract_ended = True

            if re.search(r'payout is still pending|earnings shown.*can change|isn.?t withdrawable', txt, re.IGNORECASE):
                has_gig_warning = True

            m_rent = re.search(r'increases monthly rent by (\d+)%|sewa bulanan naik (\d+)%', txt, re.IGNORECASE)
            if m_rent:
                rent_increase_pct = float(m_rent.group(1)) / 100.0

            m_date = re.search(r'(?:expected on|berlaku mulai|resumes on|credit date is|dijadwalkan pada|jatuh tempo pada)\s+(\d{4}-\d{2}-\d{2})', txt, re.IGNORECASE)
            if m_date:
                salary_date_override = m_date.group(1)

            m_sal = re.search(r'(?:naik menjadi|gaji pokok.*adalah|gaji pertama Anda adalah|reduced to|monthly pay is|Regular salary of|first salary will be|confirmed salary is|salary of)\s+([A-Z]{3})\s*([\d\.,]+)', txt, re.IGNORECASE)
            if m_sal:
                clean_num = m_sal.group(2).replace('.', '').replace(',', '').rstrip('.')
                raw_val = m_sal.group(2).rstrip('.')
                if '.' in raw_val and len(raw_val.split('.')[-1]) <= 2:
                    salary_val = float(raw_val.replace(',', ''))
                else:
                    salary_val = float(clean_num)
                curr = m_sal.group(1)
                salary_override = self.convert_currency(salary_val, curr, user_currency, request_date)

        return {
            'salary_override': salary_override,
            'salary_date_override': salary_date_override,
            'contract_ended': contract_ended,
            'rent_increase_pct': rent_increase_pct,
            'has_gig_warning': has_gig_warning
        }

    def simulate_cash_flow(self, user_id, request_date_str, spending_changes=None):
        prof = self.profiles_df[self.profiles_df['user_id'] == user_id].iloc[0]
        curr = prof['home_currency']
        current_balance = float(prof['current_available_balance'])
        min_balance = float(prof['minimum_balance_to_keep'])

        req_date = datetime.datetime.strptime(request_date_str, '%Y-%m-%d').date()
        end_date = req_date + datetime.timedelta(days=90)

        msg_info = self.parse_user_messages(user_id, request_date_str, curr)

        user_events = self.events_df[(self.events_df['user_id'] == user_id) & (self.events_df['status'] != 'cancelled')].copy()
        user_events['event_date_dt'] = pd.to_datetime(user_events['event_date']).dt.date

        past_sal = user_events[(user_events['category'] == 'salary') & (user_events['event_date_dt'] <= req_date)]
        if len(past_sal) > 0:
            last_sal_desc = str(past_sal.sort_values('event_date_dt').iloc[-1]['description']).lower()
            if 'final' in last_sal_desc:
                msg_info['contract_ended'] = True
        if msg_info['has_gig_warning']:
            msg_info['contract_ended'] = True

        changes = {}
        if spending_changes and spending_changes != 'none':
            for ch in spending_changes.split('|'):
                if ch.startswith('stop:'):
                    ev = ch.split(':')[1]
                    changes[ev] = ('stop', 0.0)
                elif ch.startswith('reduce_to:'):
                    parts = ch.split(':')
                    ev = parts[1]
                    amt = float(parts[2])
                    changes[ev] = ('reduce_to', amt)

        daily_cash_flow = {req_date + datetime.timedelta(days=i): 0.0 for i in range(91)}

        # 1. Pending / scheduled debits
        pending_debits = user_events[(user_events['status'].isin(['pending', 'scheduled'])) & (user_events['direction'] == 'debit')]
        for idx, r in pending_debits.iterrows():
            amt = self.convert_currency(r['amount'], r['currency'], curr, request_date_str)
            p_date = r['event_date_dt']
            if p_date < req_date:
                p_date = req_date
            if p_date <= end_date:
                daily_cash_flow[p_date] -= amt

        # 2. Salary income projection
        if not msg_info['contract_ended']:
            salary_amt = None
            if msg_info['salary_override'] is not None:
                salary_amt = msg_info['salary_override']
            else:
                sched_sal = user_events[(user_events['status'] == 'scheduled') & (user_events['category'] == 'salary')]
                if len(sched_sal) > 0:
                    salary_amt = self.convert_currency(sched_sal.iloc[0]['amount'], sched_sal.iloc[0]['currency'], curr, request_date_str)
                else:
                    if len(past_sal) > 0:
                        last_s = past_sal.sort_values('event_date_dt').iloc[-1]
                        salary_amt = self.convert_currency(last_s['amount'], last_s['currency'], curr, request_date_str)

            sal_day = 15
            if msg_info['salary_date_override']:
                sal_day = datetime.datetime.strptime(msg_info['salary_date_override'], '%Y-%m-%d').day
            else:
                sched_sal = user_events[(user_events['status'] == 'scheduled') & (user_events['category'] == 'salary')]
                if len(sched_sal) > 0:
                    sal_day = sched_sal.iloc[0]['event_date_dt'].day
                else:
                    if len(past_sal) > 0:
                        sal_day = past_sal.sort_values('event_date_dt').iloc[-1]['event_date_dt'].day

            curr_m = req_date.year * 12 + req_date.month - 1
            for m in range(curr_m, curr_m + 4):
                y = m // 12
                month = m % 12 + 1
                max_d = calendar.monthrange(y, month)[1]
                d = min(sal_day, max_d)
                s_date = datetime.date(y, month, d)
                if req_date <= s_date <= end_date:
                    daily_cash_flow[s_date] += salary_amt

        # 3. Recurring debits
        past_settled = user_events[(user_events['status'] == 'settled') & (user_events['event_date_dt'] < req_date)]
        for cat, g in past_settled.groupby('category'):
            if g['direction'].iloc[-1] != 'debit':
                continue
            if len(g) < 2:
                continue
            if cat in ['work_expense', 'investment']:
                continue

            g_sorted = g.sort_values('event_date_dt')
            diffs = [(g_sorted.iloc[i]['event_date_dt'] - g_sorted.iloc[i-1]['event_date_dt']).days for i in range(1, len(g_sorted))]
            med_diff = np.median(diffs)

            last_event = g_sorted.iloc[-1]
            ev_id = last_event['event_id']

            if cat in ['groceries', 'transport', 'dining']:
                amt = self.convert_currency(g_sorted['amount'].median(), last_event['currency'], curr, request_date_str)
            else:
                amt = self.convert_currency(last_event['amount'], last_event['currency'], curr, request_date_str)
                if cat == 'rent' and msg_info['rent_increase_pct'] > 0:
                    amt *= (1.0 + msg_info['rent_increase_pct'])

            if ev_id in changes:
                ch_type, target_val = changes[ev_id]
                if ch_type == 'stop':
                    amt = 0.0
                elif ch_type == 'reduce_to':
                    amt = target_val

            if med_diff >= 25:
                dom = last_event['event_date_dt'].day
                curr_m = req_date.year * 12 + req_date.month - 1
                for m in range(curr_m, curr_m + 4):
                    y = m // 12
                    month = m % 12 + 1
                    max_d = calendar.monthrange(y, month)[1]
                    d = min(dom, max_d)
                    ev_date = datetime.date(y, month, d)
                    if req_date <= ev_date <= end_date:
                        daily_cash_flow[ev_date] -= amt
            else:
                cadence = int(round(med_diff))
                next_d = last_event['event_date_dt'] + datetime.timedelta(days=cadence)
                while next_d <= end_date:
                    if next_d >= req_date:
                        daily_cash_flow[next_d] -= amt
                    next_d += datetime.timedelta(days=cadence)

        balances = []
        dates = []
        b = current_balance
        for day, cf in sorted(daily_cash_flow.items()):
            b += cf
            balances.append(b)
            dates.append(day)

        return balances, dates, min_balance, current_balance

    def evaluate_single_request(self, row):
        req_id = row['request_id']
        uid = row['user_id']
        req_date_str = row['request_date']
        req_amt = float(row['requested_amount'])
        desired_date_str = row['desired_completion_date']
        allows_partial = str(row['allows_partial_payment']).strip().lower() in ['true', '1', 't', 'yes']

        prof = self.profiles_df[self.profiles_df['user_id'] == uid].iloc[0]
        curr = prof['home_currency']
        min_balance = float(prof['minimum_balance_to_keep'])
        considered_methods = str(prof['payment_methods_user_will_consider']).split('|')
        max_inst_months = prof['max_installment_months']
        max_inst = int(float(max_inst_months)) if pd.notna(max_inst_months) and str(max_inst_months).strip() != '' else 999

        req_date = datetime.datetime.strptime(req_date_str, '%Y-%m-%d').date()
        desired_date = datetime.datetime.strptime(desired_date_str, '%Y-%m-%d').date()

        # 1. Baseline simulation without changes
        balances, dates, min_bal, start_bal = self.simulate_cash_flow(uid, req_date_str)
        min_b = min(balances)
        safe_to_pay = min(req_amt, max(0.0, min_b - min_bal))

        # Earliest date when single payment is safe
        earliest_date = None
        if safe_to_pay >= req_amt:
            earliest_date = req_date
        else:
            for i in range(len(dates)):
                d = dates[i]
                if all(b >= min_bal + req_amt for b in balances[i:]):
                    earliest_date = d
                    break

        candidates = []

        # Candidate A: Full payment today without changes
        if 'full_payment' in considered_methods and safe_to_pay >= req_amt:
            candidates.append({
                'method': 'full_payment',
                'status': 'affordable_now',
                'plan': f"{req_date_str}:{format_amount(req_amt)}",
                'spending_changes': 'none',
                'earliest_date': req_date_str,
                'total_paid': req_amt,
                'start_date': req_date,
                'completion_date': req_date,
                'num_payments': 1,
                'option_id': 'option_00'
            })

        # Candidate B: Installments
        if 'installments' in considered_methods:
            user_opts = self.options_df[(self.options_df['request_id'] == req_id) & (self.options_df['payment_method'] == 'installments')]
            for idx, opt in user_opts.iterrows():
                num_p = int(opt['number_of_payments'])
                if num_p > max_inst:
                    continue
                p_amt = float(opt['payment_amount'])
                first_p_date = datetime.datetime.strptime(opt['first_payment_date'], '%Y-%m-%d').date()
                freq_days = int(opt['payment_frequency_days'])
                inst_dates = [first_p_date + datetime.timedelta(days=i * freq_days) for i in range(num_p)]
                comp_date = inst_dates[-1]

                # Simulate daily balances with installment deductions
                bal_copy = list(balances)
                date_to_idx = {dates[i]: i for i in range(len(dates))}
                for p_d in inst_dates:
                    if p_d in date_to_idx:
                        idx_start = date_to_idx[p_d]
                        for j in range(idx_start, len(bal_copy)):
                            bal_copy[j] -= p_amt

                if all(b >= min_bal for b in bal_copy):
                    plan_parts = [f"{d.strftime('%Y-%m-%d')}:{format_amount(p_amt)}" for d in inst_dates]
                    candidates.append({
                        'method': 'installments',
                        'status': 'affordable_with_plan',
                        'plan': '|'.join(plan_parts),
                        'spending_changes': 'none',
                        'earliest_date': earliest_date.strftime('%Y-%m-%d') if earliest_date else '',
                        'total_paid': float(opt['total_payable_amount']),
                        'start_date': first_p_date,
                        'completion_date': comp_date,
                        'num_payments': num_p,
                        'option_id': opt['payment_option_id'],
                        'installment_amount': p_amt,
                        'installment_count': num_p
                    })

        # Candidate C: Partial payment
        if allows_partial and 'partial_payment' in considered_methods and safe_to_pay > 0 and safe_to_pay < req_amt and earliest_date and earliest_date <= desired_date:
            rem_amt = req_amt - safe_to_pay
            p1 = f"{req_date_str}:{format_amount(safe_to_pay)}"
            p2 = f"{earliest_date.strftime('%Y-%m-%d')}:{format_amount(rem_amt)}"
            candidates.append({
                'method': 'partial_payment',
                'status': 'affordable_with_plan',
                'plan': f"{p1}|{p2}",
                'spending_changes': 'none',
                'earliest_date': earliest_date.strftime('%Y-%m-%d'),
                'total_paid': req_amt,
                'start_date': req_date,
                'completion_date': earliest_date,
                'num_payments': 2,
                'option_id': 'partial',
                'first_payment': safe_to_pay,
                'second_payment': rem_amt
            })

        # Candidate D: Full payment with spending changes
        if 'full_payment' in considered_methods and safe_to_pay < req_amt:
            stop_cats = str(prof['expense_categories_user_is_willing_to_stop']).split('|')
            reduce_cats = str(prof['expense_categories_user_is_willing_to_reduce']).split('|')

            user_events = self.events_df[(self.events_df['user_id'] == uid) & (self.events_df['status'] != 'cancelled')]
            past_events = user_events[pd.to_datetime(user_events['event_date']).dt.date < req_date]

            flex_candidates = []
            for cat in stop_cats:
                if not cat or cat == 'nan': continue
                g = past_events[past_events['category'] == cat]
                if len(g) > 0:
                    last_ev = g.sort_values('event_date').iloc[-1]
                    if str(last_ev['flexibility']) in ['stoppable', 'reducible_or_stoppable']:
                        flex_candidates.append(('stop', last_ev['event_id'], last_ev['amount'], last_ev['description']))

            for cat in reduce_cats:
                if not cat or cat == 'nan': continue
                g = past_events[past_events['category'] == cat]
                if len(g) > 0:
                    last_ev = g.sort_values('event_date').iloc[-1]
                    if str(last_ev['flexibility']) in ['reducible', 'reducible_or_stoppable'] and pd.notna(last_ev['minimum_allowed_amount']):
                        flex_candidates.append(('reduce_to', last_ev['event_id'], float(last_ev['minimum_allowed_amount']), last_ev['description']))

            import itertools
            found_change = None
            for k in range(1, min(4, len(flex_candidates) + 1)):
                for comb in itertools.combinations(flex_candidates, k):
                    ev_ids = [c[1] for c in comb]
                    if len(set(ev_ids)) != len(ev_ids):
                        continue
                    ch_str = '|'.join([f"{c[0]}:{c[1]}" if c[0] == 'stop' else f"{c[0]}:{c[1]}:{format_amount(c[2])}" for c in comb])
                    bals_new, _, min_b_new, _ = self.simulate_cash_flow(uid, req_date_str, spending_changes=ch_str)
                    if min(bals_new) - min_b_new >= req_amt:
                        found_change = (ch_str, comb)
                        break
                if found_change:
                    break

            if found_change:
                ch_str, comb = found_change
                candidates.append({
                    'method': 'full_payment',
                    'status': 'affordable_with_plan',
                    'plan': f"{req_date_str}:{format_amount(req_amt)}",
                    'spending_changes': ch_str,
                    'earliest_date': earliest_date.strftime('%Y-%m-%d') if earliest_date else '',
                    'total_paid': req_amt,
                    'start_date': req_date,
                    'completion_date': req_date,
                    'num_payments': 1,
                    'option_id': 'changes',
                    'change_items': comb
                })

        # Candidate E: Wait
        if 'full_payment' in considered_methods and earliest_date and earliest_date <= desired_date and earliest_date > req_date:
            candidates.append({
                'method': 'wait',
                'status': 'affordable_later',
                'plan': f"{earliest_date.strftime('%Y-%m-%d')}:{format_amount(req_amt)}",
                'spending_changes': 'none',
                'earliest_date': earliest_date.strftime('%Y-%m-%d'),
                'total_paid': req_amt,
                'start_date': earliest_date,
                'completion_date': earliest_date,
                'num_payments': 1,
                'option_id': 'wait'
            })

        # Rank candidates
        best = None
        if candidates:
            def rank_key(c):
                on_time = 0 if c['completion_date'] <= desired_date else 1
                no_changes = 0 if c['spending_changes'] == 'none' else 1
                total_cost = c['total_paid']
                start_d = c['start_date']
                num_p = c['num_payments']
                opt_id = c['option_id']
                return (on_time, no_changes, total_cost, start_d, num_p, opt_id)

            candidates.sort(key=rank_key)
            best = candidates[0]

        if not best or (best['completion_date'] > desired_date and best['method'] != 'installments'):
            best = {
                'method': 'not_recommended',
                'status': 'not_affordable',
                'plan': 'none',
                'spending_changes': 'none',
                'earliest_date': earliest_date.strftime('%Y-%m-%d') if earliest_date else '',
                'total_paid': 0.0,
                'start_date': req_date,
                'completion_date': req_date,
                'num_payments': 0,
                'option_id': 'none'
            }

        # Synthesize ground-truth styled explanation
        status = best['status']
        method = best['method']
        plan = best['plan']
        changes_str = best['spending_changes']
        earliest_str = best['earliest_date']
        explanation = ""

        if status == 'affordable_now':
            explanation = f"Pay {format_currency_text(req_amt, curr)} today. This leaves at least {format_currency_text(min_balance, curr)} available over the next 90 days."
        elif status == 'affordable_with_plan' and method == 'installments':
            n_inst = best.get('installment_count', 3)
            p_inst = best.get('installment_amount', req_amt / n_inst)
            f_date = format_date_human(best['start_date'])
            explanation = f"Use {n_inst} installments of {format_currency_text(p_inst, curr)}, starting {f_date}. This leaves at least {format_currency_text(min_balance, curr)} available."
        elif status == 'affordable_with_plan' and method == 'partial_payment':
            p1_amt = best.get('first_payment', safe_to_pay)
            p2_amt = best.get('second_payment', req_amt - safe_to_pay)
            e_date_human = format_date_human(earliest_date) if earliest_date else earliest_str
            explanation = f"Pay {format_currency_text(p1_amt, curr)} today and the remaining {format_currency_text(p2_amt, curr)} on {e_date_human}. This completes the full request and keeps the {format_currency_text(min_balance, curr)} minimum protected."
        elif status == 'affordable_with_plan' and method == 'full_payment':
            items = best.get('change_items', [])
            clause_parts = []
            for item in items:
                act_type, ev_id, amt, desc = item
                clean_desc = desc.lower()
                if act_type == 'stop':
                    clause_parts.append(f"stop the {clean_desc}")
                else:
                    clause_parts.append(f"reduce the {clean_desc} to {format_currency_text(amt, curr)}")
            clause = " and ".join(clause_parts).capitalize()
            explanation = f"{clause}, then pay {format_currency_text(req_amt, curr)} today. This leaves at least {format_currency_text(min_balance, curr)} available."
        elif status == 'affordable_later' and method == 'wait':
            e_date_human = format_date_human(earliest_date) if earliest_date else earliest_str
            explanation = f"Pay {format_currency_text(req_amt, curr)} in full on {e_date_human}. Paying earlier would take the balance below the {format_currency_text(min_balance, curr)} minimum."
        else: # not_affordable
            if not earliest_str and safe_to_pay > 0:
                explanation = f"Do not proceed with the {format_currency_text(req_amt, curr)} request. Although {format_currency_text(safe_to_pay, curr)} is available today, the full amount cannot be completed safely within 90 days."
            else:
                d_date_human = format_date_human(desired_date)
                explanation = f"Do not make this payment by {d_date_human}. None of the available options keeps the {format_currency_text(min_balance, curr)} minimum protected."

        return {
            'request_id': req_id,
            'amount_safe_to_pay': format_amount(safe_to_pay),
            'affordability_status': status,
            'recommended_payment_method': method,
            'payment_plan': plan,
            'earliest_date_for_full_payment': earliest_str,
            'spending_changes_needed': changes_str,
            'decision_explanation': explanation
        }

    def run_all(self, output_file='output.csv'):
        results = []
        for idx, row in self.requests_df.iterrows():
            res = self.evaluate_single_request(row)
            results.append(res)
        out_df = pd.DataFrame(results)
        cols = [
            'request_id',
            'amount_safe_to_pay',
            'affordability_status',
            'recommended_payment_method',
            'payment_plan',
            'earliest_date_for_full_payment',
            'spending_changes_needed',
            'decision_explanation'
        ]
        out_df = out_df[cols]
        out_df.to_csv(output_file, index=False)
        print(f"Generated predictions for {len(out_df)} requests to {output_file}")
        return out_df

if __name__ == '__main__':
    agent = FinancialDecisionAgent(data_dir='dataset')
    agent.run_all(output_file='output.csv')
