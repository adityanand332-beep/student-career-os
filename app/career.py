CAREERS={
 'Python Backend Developer': ['Python','Flask','Django','SQL','Git','GitHub','Data Structures','Algorithms'],
 'Full Stack Developer': ['HTML','CSS','JavaScript','React','Node.js','SQL','Git','GitHub'],
 'Data Analyst': ['Python','SQL','Excel','Power BI','Pandas','NumPy','Communication','Problem Solving'],
 'ML Engineer': ['Python','Machine Learning','Pandas','NumPy','SQL','Data Structures','Algorithms','Git'],
 'Cybersecurity Analyst': ['Cybersecurity','Linux','Python','Networking','Git','Problem Solving'],
 'Java Developer': ['Java','SQL','Git','GitHub','Data Structures','Algorithms','Problem Solving']
}
ROADMAPS={
 'Python Backend Developer':['Python fundamentals','OOP + Data Structures','SQL + database design','Flask REST APIs','Authentication + security','Testing + deployment'],
 'Full Stack Developer':['HTML/CSS fundamentals','JavaScript + DOM','React','Node.js APIs','SQL + authentication','Deploy full-stack app'],
 'Data Analyst':['Excel + data cleaning','SQL','Python + Pandas','Statistics','Power BI dashboards','Portfolio case studies'],
 'ML Engineer':['Python + NumPy/Pandas','Statistics','Machine learning fundamentals','Model evaluation','APIs with Flask','Deployment + MLOps basics'],
 'Cybersecurity Analyst':['Linux fundamentals','Networking','Security concepts','Python scripting','Web security','Logs + incident analysis'],
 'Java Developer':['Core Java','OOP + collections','DSA','SQL + JDBC','Spring Boot basics','Testing + deployment']
}

def match(user_skills, career):
    req=CAREERS[career]; have={x.lower() for x in user_skills}; got=[x for x in req if x.lower() in have]; missing=[x for x in req if x.lower() not in have]
    return round(len(got)/len(req)*100), got, missing
