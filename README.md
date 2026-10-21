# HireOps

An SRE's toolkit for the job search: small, free, open-source tools that run on your own laptop.

## Tool 1: JD Decoder (prototype)

Give it a job description and your resume. A local AI model (Ollama) finds every skill the job asks for, with no fixed keyword list, plus its must-haves, nice-to-haves, seniority and possible red flags. Plain Python rules then check your resume for each skill, give a repeatable match score and list the skills your resume never mentions.

    python jd_decoder.py samples/job.txt --resume samples/resume.md

Your files never leave your computer. The samples in this repo are fictional.