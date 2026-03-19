def achieve_goal(goal='None',status='None'):
    if goal == 'None' or status == 'None':
        return "Please provide both goal and status."
    if status == 'achieved':
        return f"Congratulations on achieving your goal: {goal}!"
    elif status == 'in progress':
        return f"Keep going! You're making progress towards your goal: {goal}."
    elif status == 'not started':
        return f"Don't wait! Start working on your goal: {goal} today."
    