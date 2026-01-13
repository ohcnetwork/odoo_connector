
class EmployeeUtility:
    @classmethod
    def get_or_create_employee(cls, user_env, employee_data):
        try:
            hr_employee_model = user_env["hr.employee"]
            res_users_model = user_env['res.users']
            name = employee_data.name
            x_care_id = employee_data.x_care_id
            partner_x_care_id = employee_data.partner_x_care_id
            phone = employee_data.phone
            job_title = employee_data.job_title
            email = employee_data.email
            status = employee_data.status.value if employee_data.status else None

            hr_employee = hr_employee_model.with_context(active_test=False).search(
                [("x_care_id", "=", x_care_id)], limit=1
            )
            res_user_id = None
            if partner_x_care_id:
                res_user = res_users_model.search(
                    [("partner_id.x_care_id", "=", partner_x_care_id)], limit=1
                )
                if res_user:
                    res_user_id = res_user.id
            if not hr_employee:
                hr_employee = hr_employee_model.create({
                    'name': name,
                    'job_title': job_title,
                    'x_care_id': x_care_id,
                    'work_email': email,
                    'mobile_phone': phone,
                    'user_id': res_user_id,
                })
            else:
                hr_employee.name = name
                hr_employee.job_title = job_title
                hr_employee.work_email = email
                hr_employee.mobile_phone = phone
                hr_employee.user_id = res_user_id

            if status:
                if status == "retired" and hr_employee.active:
                    hr_employee.active = False
                elif status in ["draft", "active"] and not hr_employee.active:
                    hr_employee.active = True

            return hr_employee
        except Exception as e:
            return {"error": f"Error while creating/updating employee {str(e)}"}