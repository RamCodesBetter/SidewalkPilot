# MkDocs Fill Order Checklist

Editable authoring checklist for filling in the SidewalkPilot MkDocs site.

Source of page list: `mkdocs.yml`
Site docs directory: `docs/site`
Audience: public readers, technical reviewers, robotics builders, and admissions-style reviewers.
Rule: keep private prep notes out of the public docs. Write facts, evidence, limitations, and commands.

## How To Use This File

- [ ] Work top to bottom by phase, not alphabetically.
- [ ] For each page, first create the file if it is missing.
- [ ] Fill the page checklist before moving the page to review.
- [ ] Replace placeholders with real paths, commands, metrics, screenshots, videos, and field notes.
- [ ] After a phase is done, run `mkdocs serve` and click through that phase.
- [ ] Before publishing, search for stale words: `TODO`, `pending`, `future`, `should`, `needs`, and private notes.

## Phase Summary

- [ ] Phase 1 - Public First Impression: 23 pages
- [ ] Phase 2 - Safety And Field Reality: 42 pages
- [ ] Phase 3 - Data, Models, And Evaluation: 92 pages
- [ ] Phase 4 - Autonomy Runtime Stack: 49 pages
- [ ] Phase 5 - Hardware, Operations, And Runbooks: 39 pages
- [ ] Phase 6 - Math, Code Reference, Exhibits, Publishing, Roadmap: 47 pages

## Add Soon After README/Docs Are Ready

- [ ] Add `ai-and-models/model-zoo/v2-2.md` to `mkdocs.yml` after you decide the wording for SidewalkPilot-v2.2.
  - [ ] Include checkpoint name, training command summary, current-label metrics, and field result for v2.2.
  - [ ] Link Hugging Face repo after README/model card exists for v2.2.
- [ ] Add `ai-and-models/model-zoo/v2-2b.md` to `mkdocs.yml` after you decide the wording for SidewalkPilot-v2.2b.
  - [ ] Include checkpoint name, training command summary, current-label metrics, and field result for v2.2b.
  - [ ] Link Hugging Face repo after README/model card exists for v2.2b.
- [ ] Add `ai-and-models/model-zoo/v2-3.md` to `mkdocs.yml` after you decide the wording for SidewalkPilot-v2.3.
  - [ ] Include checkpoint name, training command summary, current-label metrics, and field result for v2.3.
  - [ ] Link Hugging Face repo after README/model card exists for v2.3.
- [ ] Add `ai-and-models/model-zoo/v2-3b.md` to `mkdocs.yml` after you decide the wording for SidewalkPilot-v2.3b.
  - [ ] Include checkpoint name, training command summary, current-label metrics, and field result for v2.3b.
  - [ ] Link Hugging Face repo after README/model card exists for v2.3b.

## Phase 1 - Public First Impression

Write the pages a first-time visitor reads before deciding the project is real.

- [ ] Phase started
- [ ] Phase drafted
- [ ] Phase reviewed in local MkDocs server

### 001. Home

- [ ] Page: `docs/site/index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] State the one-sentence mission and what the car actually does.
  - [ ] Add one current best-status box: latest model, best rollback, known field risk.
  - [ ] Link the report PDF, model cards, dataset pages, and safety overview.
  - [ ] Add one demo/video placeholder and one architecture diagram placeholder.
  - [ ] End with clear research scope: sidewalk RC platform, not a public-road product.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 002. Start Here > Project Overview

- [ ] Page: `docs/site/start-here/project-overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the public explanation for Project Overview.
  - [ ] Use plain language first, then link deeper technical pages.
  - [ ] Mention current status, evidence, limitations, and next page to read.
  - [ ] Add one diagram/table/video placeholder where useful.
  - [ ] Keep it accurate for both public readers and technical reviewers.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 003. Start Here > Mission

- [ ] Page: `docs/site/start-here/mission.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the public explanation for Mission.
  - [ ] Use plain language first, then link deeper technical pages.
  - [ ] Mention current status, evidence, limitations, and next page to read.
  - [ ] Add one diagram/table/video placeholder where useful.
  - [ ] Keep it accurate for both public readers and technical reviewers.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 004. Start Here > System At A Glance

- [ ] Page: `docs/site/start-here/system-at-a-glance.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the public explanation for System At A Glance.
  - [ ] Use plain language first, then link deeper technical pages.
  - [ ] Mention current status, evidence, limitations, and next page to read.
  - [ ] Add one diagram/table/video placeholder where useful.
  - [ ] Keep it accurate for both public readers and technical reviewers.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 005. Start Here > Current Status

- [ ] Page: `docs/site/start-here/current-status.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the public explanation for Current Status.
  - [ ] Use plain language first, then link deeper technical pages.
  - [ ] Mention current status, evidence, limitations, and next page to read.
  - [ ] Add one diagram/table/video placeholder where useful.
  - [ ] Keep it accurate for both public readers and technical reviewers.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 006. Start Here > Build Timeline

- [ ] Page: `docs/site/start-here/build-timeline.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the public explanation for Build Timeline.
  - [ ] Use plain language first, then link deeper technical pages.
  - [ ] Mention current status, evidence, limitations, and next page to read.
  - [ ] Add one diagram/table/video placeholder where useful.
  - [ ] Keep it accurate for both public readers and technical reviewers.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 007. Project Evidence > Reader Paths > 30 Second Overview

- [ ] Page: `docs/site/portfolio-evidence/reader-paths/30-second-overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the audience for 30 Second Overview: quick visitor, technical reviewer, or deep reader.
  - [ ] List the exact pages to read in order with one-line reasons.
  - [ ] Include links to evidence pages, metrics, safety limits, and model history.
  - [ ] Keep the page short enough to be a navigation guide, not a full report.
  - [ ] Add a final next-click link to the most important proof page.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 008. Project Evidence > Reader Paths > 5 Minute Technical Tour

- [ ] Page: `docs/site/portfolio-evidence/reader-paths/5-minute-technical-tour.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the audience for 5 Minute Technical Tour: quick visitor, technical reviewer, or deep reader.
  - [ ] List the exact pages to read in order with one-line reasons.
  - [ ] Include links to evidence pages, metrics, safety limits, and model history.
  - [ ] Keep the page short enough to be a navigation guide, not a full report.
  - [ ] Add a final next-click link to the most important proof page.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 009. Project Evidence > Reader Paths > Deep Engineering Tour

- [ ] Page: `docs/site/portfolio-evidence/reader-paths/deep-engineering-tour.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the audience for Deep Engineering Tour: quick visitor, technical reviewer, or deep reader.
  - [ ] List the exact pages to read in order with one-line reasons.
  - [ ] Include links to evidence pages, metrics, safety limits, and model history.
  - [ ] Keep the page short enough to be a navigation guide, not a full report.
  - [ ] Add a final next-click link to the most important proof page.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 010. Project Evidence > Reader Paths > Evidence Map

- [ ] Page: `docs/site/portfolio-evidence/reader-paths/evidence-map.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the audience for Evidence Map: quick visitor, technical reviewer, or deep reader.
  - [ ] List the exact pages to read in order with one-line reasons.
  - [ ] Include links to evidence pages, metrics, safety limits, and model history.
  - [ ] Keep the page short enough to be a navigation guide, not a full report.
  - [ ] Add a final next-click link to the most important proof page.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 011. Project Evidence > Demonstrations > Hero Run

- [ ] Page: `docs/site/portfolio-evidence/demonstrations/hero-run.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Hero Run: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 012. Project Evidence > Demonstrations > Successful Autonomous Runs

- [ ] Page: `docs/site/portfolio-evidence/demonstrations/successful-autonomous-runs.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Successful Autonomous Runs: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 013. Project Evidence > Demonstrations > Safety Override Demo

- [ ] Page: `docs/site/portfolio-evidence/demonstrations/safety-override-demo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Safety Override Demo: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 014. Project Evidence > Demonstrations > Navigation Demo

- [ ] Page: `docs/site/portfolio-evidence/demonstrations/navigation-demo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Navigation Demo: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 015. Project Evidence > Demonstrations > Dashboard Demo

- [ ] Page: `docs/site/portfolio-evidence/demonstrations/dashboard-demo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/z2w_dashboard.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Dashboard Demo: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 016. Project Evidence > Demonstrations > Night Failure Demo

- [ ] Page: `docs/site/portfolio-evidence/demonstrations/night-failure-demo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Night Failure Demo: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 017. Project Evidence > Claims And Proof > Autonomy Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/autonomy-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the exact claim for Autonomy Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 018. Project Evidence > Claims And Proof > Safety Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/safety-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the exact claim for Safety Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 019. Project Evidence > Claims And Proof > Data Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/data-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the exact claim for Data Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 020. Project Evidence > Claims And Proof > Model Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/model-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the exact claim for Model Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 021. Project Evidence > Claims And Proof > Navigation Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/navigation-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Write the exact claim for Navigation Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 022. Project Evidence > Claims And Proof > Hardware Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/hardware-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Write the exact claim for Hardware Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 023. Project Evidence > Claims And Proof > Reproducibility Claim

- [ ] Page: `docs/site/portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the exact claim for Reproducibility Claim in one sentence.
  - [ ] List the evidence files, videos, tests, metrics, or code paths that support it.
  - [ ] Add the strongest counterexample or limitation so the claim is honest.
  - [ ] Link to the detailed technical page that explains the mechanism.
  - [ ] Add a proof checklist with status: measured, demonstrated, or documented.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

## Phase 2 - Safety And Field Reality

Show the system is tested honestly, fails safely, and is not oversold.

- [ ] Phase started
- [ ] Phase drafted
- [ ] Phase reviewed in local MkDocs server

### 024. Testing > Field Testing > Overview

- [ ] Page: `docs/site/testing/field-testing/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Overview means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 025. Testing > Field Testing > Preflight Checklist

- [ ] Page: `docs/site/testing/field-testing/preflight-checklist.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Preflight Checklist means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 026. Testing > Field Testing > Model Retest Plan

- [ ] Page: `docs/site/testing/field-testing/model-retest-plan.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Model Retest Plan means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 027. Testing > Field Testing > Manual Takeovers

- [ ] Page: `docs/site/testing/field-testing/manual-takeovers.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Manual Takeovers means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 028. Testing > Field Testing > Field Logs

- [ ] Page: `docs/site/testing/field-testing/field-logs.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Field Logs means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 029. Testing > Failures > Overview

- [ ] Page: `docs/site/testing/failures/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Overview means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 030. Testing > Failures > Shadow Failures

- [ ] Page: `docs/site/testing/failures/shadow-failures.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Shadow Failures means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 031. Testing > Failures > Harsh Sidewalk

- [ ] Page: `docs/site/testing/failures/harsh-sidewalk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Harsh Sidewalk means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 032. Testing > Failures > Evening Failures

- [ ] Page: `docs/site/testing/failures/evening-failures.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Evening Failures means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 033. Testing > Failures > Driveway Confusion

- [ ] Page: `docs/site/testing/failures/driveway-confusion.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Driveway Confusion means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 034. Testing > Failures > Road Entry Risk

- [ ] Page: `docs/site/testing/failures/road-entry-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Road Entry Risk means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 035. Testing > Failures > LiDAR Disconnects

- [ ] Page: `docs/site/testing/failures/lidar-disconnects.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/lidar.py`, `code/controller/current/rc_car_app/runtime.py`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: LiDAR Disconnects.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 036. Testing > Bench Tests > Overview

- [ ] Page: `docs/site/testing/bench-tests/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Overview means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 037. Testing > Bench Tests > Camera Preview

- [ ] Page: `docs/site/testing/bench-tests/camera-preview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Camera Preview means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 038. Testing > Bench Tests > Model Steering

- [ ] Page: `docs/site/testing/bench-tests/model-steering.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Model Steering means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 039. Testing > Bench Tests > Servo

- [ ] Page: `docs/site/testing/bench-tests/servo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Servo means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 040. Testing > Bench Tests > LiDAR Viewer

- [ ] Page: `docs/site/testing/bench-tests/lidar-viewer.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/lidar.py`, `code/controller/current/rc_car_app/runtime.py`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: LiDAR Viewer.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 041. Testing > Bench Tests > GPS Compass

- [ ] Page: `docs/site/testing/bench-tests/gps-compass.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what GPS Compass means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 042. Testing > Bench Tests > Dashboard

- [ ] Page: `docs/site/testing/bench-tests/dashboard.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/z2w_dashboard.py`, `code/controller/current/rc_car_app/runtime.py`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what Dashboard means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 043. Testing > Bench Tests > A Star CLI

- [ ] Page: `docs/site/testing/bench-tests/a-star-cli.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: A Star CLI.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 044. Testing > Bench Tests > GeoJSON Graph

- [ ] Page: `docs/site/testing/bench-tests/geojson-graph.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define what GeoJSON Graph means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 045. Safety Case > Safety Overview

- [ ] Page: `docs/site/safety-case/safety-overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Safety Overview.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 046. Safety Case > Hazard Analysis > Road Entry

- [ ] Page: `docs/site/safety-case/hazard-analysis/road-entry.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Road Entry.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 047. Safety Case > Hazard Analysis > Pedestrian Risk

- [ ] Page: `docs/site/safety-case/hazard-analysis/pedestrian-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Pedestrian Risk.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 048. Safety Case > Hazard Analysis > Crosswalk Risk

- [ ] Page: `docs/site/safety-case/hazard-analysis/crosswalk-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Crosswalk Risk.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 049. Safety Case > Hazard Analysis > Night Driving Risk

- [ ] Page: `docs/site/safety-case/hazard-analysis/night-driving-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Night Driving Risk.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 050. Safety Case > Hazard Analysis > Sensor Disconnect Risk

- [ ] Page: `docs/site/safety-case/hazard-analysis/sensor-disconnect-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Sensor Disconnect Risk.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 051. Safety Case > Fault Handling > Manual Override

- [ ] Page: `docs/site/safety-case/fault-handling/manual-override.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Manual Override.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 052. Safety Case > Fault Handling > Hard Brake

- [ ] Page: `docs/site/safety-case/fault-handling/hard-brake.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/lidar.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Hard Brake.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 053. Safety Case > Fault Handling > Stale Camera Frame

- [ ] Page: `docs/site/safety-case/fault-handling/stale-camera-frame.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Stale Camera Frame.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 054. Safety Case > Fault Handling > Stale LiDAR Scan

- [ ] Page: `docs/site/safety-case/fault-handling/stale-lidar-scan.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/lidar.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Stale LiDAR Scan.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 055. Safety Case > Fault Handling > Dashboard Telemetry Loss

- [ ] Page: `docs/site/safety-case/fault-handling/dashboard-telemetry-loss.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/z2w_dashboard.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Dashboard Telemetry Loss.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 056. Safety Case > Fault Handling > GPS Loss

- [ ] Page: `docs/site/safety-case/fault-handling/gps-loss.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: GPS Loss.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 057. Safety Case > Operating Limits > Where It Can Run

- [ ] Page: `docs/site/safety-case/operating-limits/where-it-can-run.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Where It Can Run.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 058. Safety Case > Operating Limits > Where It Cannot Run

- [ ] Page: `docs/site/safety-case/operating-limits/where-it-cannot-run.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Where It Cannot Run.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 059. Safety Case > Operating Limits > Speed Limits

- [ ] Page: `docs/site/safety-case/operating-limits/speed-limits.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Speed Limits.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 060. Safety Case > Operating Limits > Lighting Limits

- [ ] Page: `docs/site/safety-case/operating-limits/lighting-limits.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Lighting Limits.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 061. Safety Case > Operating Limits > Weather Limits

- [ ] Page: `docs/site/safety-case/operating-limits/weather-limits.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Weather Limits.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 062. Safety And Ethics > Research Scope

- [ ] Page: `docs/site/safety-and-ethics/research-scope.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Research Scope.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 063. Safety And Ethics > Limits

- [ ] Page: `docs/site/safety-and-ethics/limits.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Limits.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 064. Safety And Ethics > Privacy

- [ ] Page: `docs/site/safety-and-ethics/privacy.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Privacy.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 065. Safety And Ethics > Public Roads

- [ ] Page: `docs/site/safety-and-ethics/public-roads.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the safety/ethics topic: Public Roads.
  - [ ] State the hazard or limit in concrete physical terms.
  - [ ] Name the mitigation: manual override, hard brake, route handoff, operating limit, or data rule.
  - [ ] Link the code path or field test that proves the mitigation exists.
  - [ ] Add a limitation statement that avoids overselling autonomy.
  - [ ] Add one checklist item for preflight or operator behavior.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

## Phase 3 - Data, Models, And Evaluation

Document the label set, training pipeline, model history, and measured performance.

- [ ] Phase started
- [ ] Phase drafted
- [ ] Phase reviewed in local MkDocs server

### 066. AI And Models > Training Pipeline > Overview

- [ ] Page: `docs/site/ai-and-models/training-pipeline/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Overview does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 067. AI And Models > Training Pipeline > Training Script

- [ ] Page: `docs/site/ai-and-models/training-pipeline/training-script.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Training Script does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 068. AI And Models > Training Pipeline > Input Labels

- [ ] Page: `docs/site/ai-and-models/training-pipeline/input-labels.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Input Labels does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 069. AI And Models > Training Pipeline > Corrections

- [ ] Page: `docs/site/ai-and-models/training-pipeline/corrections.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Corrections does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 070. AI And Models > Training Pipeline > Augmentation

- [ ] Page: `docs/site/ai-and-models/training-pipeline/augmentation.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Augmentation does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 071. AI And Models > Training Pipeline > Source Weights

- [ ] Page: `docs/site/ai-and-models/training-pipeline/source-weights.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Source Weights does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 072. AI And Models > Training Pipeline > Sampler

- [ ] Page: `docs/site/ai-and-models/training-pipeline/sampler.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Sampler does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 073. AI And Models > Training Pipeline > Metrics

- [ ] Page: `docs/site/ai-and-models/training-pipeline/metrics.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Explain what Metrics does inside train_autonomy_v2.py.
  - [ ] List exact command-line flags, defaults, units, and safe example values.
  - [ ] Show the inputs: roots, corrections JSON, CARLA source, manual image folder.
  - [ ] Show the outputs: final checkpoint, best checkpoint, metrics, logs.
  - [ ] Add one command example that can be run on the NVIDIA PC.
  - [ ] Add common failure modes: wrong root, missing image, duplicate label, bad source weight.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 074. AI And Models > Architecture > CNN

- [ ] Page: `docs/site/ai-and-models/architecture/cnn.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: CNN.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 075. AI And Models > Architecture > Tensor Shape

- [ ] Page: `docs/site/ai-and-models/architecture/tensor-shape.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: Tensor Shape.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 076. AI And Models > Architecture > Conv Layers

- [ ] Page: `docs/site/ai-and-models/architecture/conv-layers.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: Conv Layers.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 077. AI And Models > Architecture > BatchNorm

- [ ] Page: `docs/site/ai-and-models/architecture/batchnorm.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: BatchNorm.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 078. AI And Models > Architecture > ELU

- [ ] Page: `docs/site/ai-and-models/architecture/elu.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: ELU.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 079. AI And Models > Architecture > Linear Head

- [ ] Page: `docs/site/ai-and-models/architecture/linear-head.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: Linear Head.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 080. AI And Models > Architecture > Tanh Output

- [ ] Page: `docs/site/ai-and-models/architecture/tanh-output.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the neural-net concept: Tanh Output.
  - [ ] Connect the concept to the exact CNN steering model layers.
  - [ ] Show tensor dimensions or layer inputs/outputs where useful.
  - [ ] Explain why it matters for steering prediction, not generic ML theory.
  - [ ] Add one failure/overfitting risk related to this component.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 081. AI And Models > Model Zoo > Overview

- [ ] Page: `docs/site/ai-and-models/model-zoo/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for Overview and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 082. AI And Models > Model Zoo > v1.0

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-0.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.0 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 083. AI And Models > Model Zoo > v1.0b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-0b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.0b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 084. AI And Models > Model Zoo > v1.1

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-1.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.1 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 085. AI And Models > Model Zoo > v1.1b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-1b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.1b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 086. AI And Models > Model Zoo > v1.2

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-2.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.2 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 087. AI And Models > Model Zoo > v1.2b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-2b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.2b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 088. AI And Models > Model Zoo > v1.3

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-3.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.3 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 089. AI And Models > Model Zoo > v1.3b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-3b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.3b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 090. AI And Models > Model Zoo > v1.4

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-4.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.4 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 091. AI And Models > Model Zoo > v1.4b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-4b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.4b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 092. AI And Models > Model Zoo > v1.5

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-5.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.5 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 093. AI And Models > Model Zoo > v1.5b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-5b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.5b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 094. AI And Models > Model Zoo > v1.6

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-6.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.6 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 095. AI And Models > Model Zoo > v1.6b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-6b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.6b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 096. AI And Models > Model Zoo > v1.7

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-7.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.7 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 097. AI And Models > Model Zoo > v1.7b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-7b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.7b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 098. AI And Models > Model Zoo > v1.8

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-8.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.8 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 099. AI And Models > Model Zoo > v1.8b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-8b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.8b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 100. AI And Models > Model Zoo > v1.9

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-9.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.9 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 101. AI And Models > Model Zoo > v1.9b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v1-9b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v1.9b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 102. AI And Models > Model Zoo > v2.0

- [ ] Page: `docs/site/ai-and-models/model-zoo/v2-0.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v2.0 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 103. AI And Models > Model Zoo > v2.0b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v2-0b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v2.0b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 104. AI And Models > Model Zoo > v2.1

- [ ] Page: `docs/site/ai-and-models/model-zoo/v2-1.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v2.1 and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 105. AI And Models > Model Zoo > v2.1b

- [ ] Page: `docs/site/ai-and-models/model-zoo/v2-1b.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Identify checkpoint file for v2.1b and whether it is final or best checkpoint.
  - [ ] Record training data changes, label-set status, augmentation/preprocessing, and output scale.
  - [ ] Copy the current offline metrics from docs/steering_eval_current_labels.json.
  - [ ] Write the field-test outcome if tested; otherwise leave a neutral blank field for later.
  - [ ] Explain what this version fixed and what failure remained.
  - [ ] Link the Hugging Face model card after it exists.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 106. Model Evaluation > Offline Evaluation > Overview

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Overview.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 107. Model Evaluation > Offline Evaluation > MAE

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/mae.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: MAE.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 108. Model Evaluation > Offline Evaluation > Median AE

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/median-ae.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Median AE.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 109. Model Evaluation > Offline Evaluation > Max AE

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/max-ae.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Max AE.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 110. Model Evaluation > Offline Evaluation > Signed Error

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/signed-error.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Signed Error.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 111. Model Evaluation > Offline Evaluation > Within Degree Buckets

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/within-degree-buckets.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Within Degree Buckets.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 112. Model Evaluation > Offline Evaluation > Per Dataset Breakdown

- [ ] Page: `docs/site/model-evaluation/offline-evaluation/per-dataset-breakdown.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Per Dataset Breakdown.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 113. Model Evaluation > Field Evaluation > Overview

- [ ] Page: `docs/site/model-evaluation/field-evaluation/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Overview.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 114. Model Evaluation > Field Evaluation > Test Route

- [ ] Page: `docs/site/model-evaluation/field-evaluation/test-route.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Test Route.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 115. Model Evaluation > Field Evaluation > Manual Takeover Count

- [ ] Page: `docs/site/model-evaluation/field-evaluation/manual-takeover-count.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Manual Takeover Count.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 116. Model Evaluation > Field Evaluation > Road Entry Risk

- [ ] Page: `docs/site/model-evaluation/field-evaluation/road-entry-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Road Entry Risk.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 117. Model Evaluation > Field Evaluation > Smoothness

- [ ] Page: `docs/site/model-evaluation/field-evaluation/smoothness.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Smoothness.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 118. Model Evaluation > Field Evaluation > Curb Hugging

- [ ] Page: `docs/site/model-evaluation/field-evaluation/curb-hugging.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Curb Hugging.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 119. Model Evaluation > Field Evaluation > Shadow Robustness

- [ ] Page: `docs/site/model-evaluation/field-evaluation/shadow-robustness.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Shadow Robustness.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 120. Model Evaluation > Field Evaluation > Evening Robustness

- [ ] Page: `docs/site/model-evaluation/field-evaluation/evening-robustness.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Evening Robustness.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 121. Model Evaluation > Comparisons > 1.9 vs 2.0 vs 2.1

- [ ] Page: `docs/site/model-evaluation/comparisons/1-9-vs-2-0-vs-2-1.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: 1.9 vs 2.0 vs 2.1.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 122. Model Evaluation > Comparisons > B Versions

- [ ] Page: `docs/site/model-evaluation/comparisons/b-versions.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: B Versions.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 123. Model Evaluation > Comparisons > Raw BGR vs CLAHE

- [ ] Page: `docs/site/model-evaluation/comparisons/raw-bgr-vs-clahe.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Raw BGR vs CLAHE.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 124. Model Evaluation > Comparisons > Offline vs Field

- [ ] Page: `docs/site/model-evaluation/comparisons/offline-vs-field.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Offline vs Field.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 125. Model Evaluation > Comparisons > Model Selection Rubric

- [ ] Page: `docs/site/model-evaluation/comparisons/model-selection-rubric.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the metric/evaluation concept: Model Selection Rubric.
  - [ ] Give the formula or counting rule in plain language.
  - [ ] Show how it appears in docs/steering_eval_current_labels.json and the PDF report.
  - [ ] Explain what the metric catches and what it misses in real field behavior.
  - [ ] Add one example comparing 2.3, 2.3b, 2.2b, and a rollback model.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 126. Data > Dataset Overview

- [ ] Page: `docs/site/data/dataset-overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what Dataset Overview means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 127. Data > Corrections JSON

- [ ] Page: `docs/site/data/corrections-json.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what Corrections JSON means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 128. Data > Manual Image Folder

- [ ] Page: `docs/site/data/manual-image-folder.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what Manual Image Folder means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 129. Data > D0328

- [ ] Page: `docs/site/data/datasets/d0328.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0328 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 130. Data > D0329

- [ ] Page: `docs/site/data/datasets/d0329.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0329 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 131. Data > D0425

- [ ] Page: `docs/site/data/datasets/d0425.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0425 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 132. Data > D0426

- [ ] Page: `docs/site/data/datasets/d0426.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0426 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 133. Data > D0427

- [ ] Page: `docs/site/data/datasets/d0427.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0427 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 134. Data > D0429

- [ ] Page: `docs/site/data/datasets/d0429.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0429 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 135. Data > D0502 12

- [ ] Page: `docs/site/data/datasets/d0502-12.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0502 12 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 136. Data > D0502 19

- [ ] Page: `docs/site/data/datasets/d0502-19.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0502 19 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 137. Data > D0503

- [ ] Page: `docs/site/data/datasets/d0503.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0503 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 138. Data > D0506

- [ ] Page: `docs/site/data/datasets/d0506.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what D0506 means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 139. Data > Relabeling > Workflow

- [ ] Page: `docs/site/data/relabeling/workflow.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what Workflow means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 140. Data > Relabeling > Merge Rules

- [ ] Page: `docs/site/data/relabeling/merge-rules.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what Merge Rules means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 141. Data > Relabeling > Temporary JSON Cleanup

- [ ] Page: `docs/site/data/relabeling/temp-json-cleanup.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what Temporary JSON Cleanup means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 142. Data > Relabeling > First Dataset Relabel

- [ ] Page: `docs/site/data/relabeling/first-dataset-relabel.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define what First Dataset Relabel means in the SidewalkPilot project.
  - [ ] Name the source-of-truth files, data, tests, or hardware involved.
  - [ ] Document inputs, outputs, settings, and commands if applicable.
  - [ ] Add evidence: metric, field log, image, video, diagram, or code link.
  - [ ] Add limitations, failure modes, and how to verify the page is correct.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 143. Data Governance > Labeling > Label Schema

- [ ] Page: `docs/site/data-governance/labeling/label-schema.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Label Schema.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 144. Data Governance > Labeling > Correction Schema

- [ ] Page: `docs/site/data-governance/labeling/correction-schema.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Correction Schema.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 145. Data Governance > Labeling > Relabel Review

- [ ] Page: `docs/site/data-governance/labeling/relabel-review.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Relabel Review.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 146. Data Governance > Labeling > Duplicate Handling

- [ ] Page: `docs/site/data-governance/labeling/duplicate-handling.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Duplicate Handling.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 147. Data Governance > Labeling > Bad Label Examples

- [ ] Page: `docs/site/data-governance/labeling/bad-label-examples.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Bad Label Examples.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 148. Data Governance > Dataset Versioning > Version Rules

- [ ] Page: `docs/site/data-governance/dataset-versioning/version-rules.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Version Rules.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 149. Data Governance > Dataset Versioning > Dmmdd Naming

- [ ] Page: `docs/site/data-governance/dataset-versioning/dmmdd-naming.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Dmmdd Naming.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 150. Data Governance > Dataset Versioning > Historical Metrics

- [ ] Page: `docs/site/data-governance/dataset-versioning/historical-metrics.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Historical Metrics.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 151. Data Governance > Dataset Versioning > Active Label Set

- [ ] Page: `docs/site/data-governance/dataset-versioning/active-label-set.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Active Label Set.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 152. Data Governance > Dataset Versioning > Removed Labels

- [ ] Page: `docs/site/data-governance/dataset-versioning/removed-labels.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Removed Labels.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 153. Data Governance > Data Quality > Image Quality Checks

- [ ] Page: `docs/site/data-governance/data-quality/image-quality-checks.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Image Quality Checks.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 154. Data Governance > Data Quality > Lighting Coverage

- [ ] Page: `docs/site/data-governance/data-quality/lighting-coverage.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Lighting Coverage.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 155. Data Governance > Data Quality > Turn Coverage

- [ ] Page: `docs/site/data-governance/data-quality/turn-coverage.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Turn Coverage.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 156. Data Governance > Data Quality > Train Val Leakage

- [ ] Page: `docs/site/data-governance/data-quality/train-val-leakage.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Train Val Leakage.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 157. Data Governance > Data Quality > Sync Audit

- [ ] Page: `docs/site/data-governance/data-quality/sync-audit.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the dataset/label topic: Sync Audit.
  - [ ] List exact file paths: image folder, correction JSON, related temp JSON if any.
  - [ ] Record counts, source names, date code, and purpose.
  - [ ] Explain merge/relabel rules and what gets deleted after merging.
  - [ ] Add one quality check: missing image, duplicate label, wrong steering value, stale source.
  - [ ] Link affected model versions and evaluation pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

## Phase 4 - Autonomy Runtime Stack

Explain how the car senses, decides, steers, brakes, hands off, and recovers.

- [ ] Phase started
- [ ] Phase drafted
- [ ] Phase reviewed in local MkDocs server

### 158. Autonomy Stack > Architecture > Layered Autonomy

- [ ] Page: `docs/site/autonomy-stack/architecture/layered-autonomy.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Layered Autonomy.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 159. Autonomy Stack > Architecture > Data Flow

- [ ] Page: `docs/site/autonomy-stack/architecture/data-flow.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Data Flow.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 160. Autonomy Stack > Architecture > Decision Priority

- [ ] Page: `docs/site/autonomy-stack/architecture/decision-priority.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Decision Priority.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 161. Autonomy Stack > Architecture > Runtime States

- [ ] Page: `docs/site/autonomy-stack/architecture/runtime-states.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Runtime States.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 162. Autonomy Stack > Architecture > Failure Boundaries

- [ ] Page: `docs/site/autonomy-stack/architecture/failure-boundaries.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Failure Boundaries.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 163. Autonomy Stack > Camera Steering > Overview

- [ ] Page: `docs/site/autonomy-stack/camera-steering/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Overview.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 164. Autonomy Stack > Camera Steering > Frame Capture

- [ ] Page: `docs/site/autonomy-stack/camera-steering/frame-capture.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Frame Capture.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 165. Autonomy Stack > Camera Steering > Preprocessing

- [ ] Page: `docs/site/autonomy-stack/camera-steering/preprocessing.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Preprocessing.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 166. Autonomy Stack > Camera Steering > Model Inference

- [ ] Page: `docs/site/autonomy-stack/camera-steering/model-inference.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Model Inference.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 167. Autonomy Stack > Camera Steering > Servo Output

- [ ] Page: `docs/site/autonomy-stack/camera-steering/servo-output.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Servo Output.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 168. Autonomy Stack > Camera Steering > Series Differences

- [ ] Page: `docs/site/autonomy-stack/camera-steering/series-differences.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Series Differences.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 169. Autonomy Stack > LiDAR Safety > Overview

- [ ] Page: `docs/site/autonomy-stack/lidar-safety/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/lidar.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Overview.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 170. Autonomy Stack > LiDAR Safety > Packet Parsing

- [ ] Page: `docs/site/autonomy-stack/lidar-safety/packet-parsing.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/lidar.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Packet Parsing.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 171. Autonomy Stack > LiDAR Safety > Distance Regions

- [ ] Page: `docs/site/autonomy-stack/lidar-safety/distance-regions.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/lidar.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Distance Regions.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 172. Autonomy Stack > LiDAR Safety > AEB

- [ ] Page: `docs/site/autonomy-stack/lidar-safety/aeb.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/lidar.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: AEB.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 173. Autonomy Stack > LiDAR Safety > Override Steering

- [ ] Page: `docs/site/autonomy-stack/lidar-safety/override-steering.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/lidar.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Override Steering.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 174. Autonomy Stack > LiDAR Safety > Reconnect Behavior

- [ ] Page: `docs/site/autonomy-stack/lidar-safety/reconnect-behavior.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/lidar.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: Reconnect Behavior.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 175. Autonomy Stack > Navigation > Overview

- [ ] Page: `docs/site/autonomy-stack/navigation/overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Overview.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 176. Autonomy Stack > Navigation > GPS Reader

- [ ] Page: `docs/site/autonomy-stack/navigation/gps-reader.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: GPS Reader.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 177. Autonomy Stack > Navigation > Graph Format

- [ ] Page: `docs/site/autonomy-stack/navigation/graph-format.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Graph Format.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 178. Autonomy Stack > Navigation > A Star

- [ ] Page: `docs/site/autonomy-stack/navigation/a-star.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: A Star.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 179. Autonomy Stack > Navigation > Turn Penalties

- [ ] Page: `docs/site/autonomy-stack/navigation/turn-penalties.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Turn Penalties.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 180. Autonomy Stack > Navigation > AI Manual Segments

- [ ] Page: `docs/site/autonomy-stack/navigation/ai-manual-segments.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: AI Manual Segments.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 181. Autonomy Stack > Navigation > Crosswalk Handoff

- [ ] Page: `docs/site/autonomy-stack/navigation/crosswalk-handoff.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Crosswalk Handoff.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 182. Autonomy Stack > Navigation > Resume Radius

- [ ] Page: `docs/site/autonomy-stack/navigation/resume-radius.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Resume Radius.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 183. Autonomy Stack > Navigation > House Snapping

- [ ] Page: `docs/site/autonomy-stack/navigation/house-snapping.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: House Snapping.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 184. Runtime Code > Controller Entrypoint

- [ ] Page: `docs/site/runtime-code/controller-entrypoint.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Controller Entrypoint.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 185. Runtime Code > Runtime Loop

- [ ] Page: `docs/site/runtime-code/runtime-loop.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Runtime Loop.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 186. Runtime Code > Config > Build Flags

- [ ] Page: `docs/site/runtime-code/config/build-flags.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Build Flags.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 187. Runtime Code > Config > GPIO Pins

- [ ] Page: `docs/site/runtime-code/config/gpio-pins.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: GPIO Pins.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 188. Runtime Code > Config > Servo Settings

- [ ] Page: `docs/site/runtime-code/config/servo-settings.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Servo Settings.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 189. Runtime Code > Config > Dashboard Settings

- [ ] Page: `docs/site/runtime-code/config/dashboard-settings.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/z2w_dashboard.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Dashboard Settings.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 190. Runtime Code > Config > Logging Settings

- [ ] Page: `docs/site/runtime-code/config/logging-settings.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Logging Settings.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 191. Runtime Code > Hardware > Hardware Class

- [ ] Page: `docs/site/runtime-code/hardware/hardware-class.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Hardware Class.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 192. Runtime Code > Hardware > PCA9685 Servo

- [ ] Page: `docs/site/runtime-code/hardware/pca9685-servo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: PCA9685 Servo.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 193. Runtime Code > Hardware > Motor PWM

- [ ] Page: `docs/site/runtime-code/hardware/motor-pwm.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Motor PWM.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 194. Runtime Code > Hardware > Hall Sensor

- [ ] Page: `docs/site/runtime-code/hardware/hall-sensor.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Hall Sensor.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 195. Runtime Code > Hardware > Cleanup

- [ ] Page: `docs/site/runtime-code/hardware/cleanup.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/hardware.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Cleanup.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 196. Runtime Code > Vision > Model Choices

- [ ] Page: `docs/site/runtime-code/vision/model-choices.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Model Choices.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 197. Runtime Code > Vision > Camera Capture

- [ ] Page: `docs/site/runtime-code/vision/camera-capture.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Camera Capture.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 198. Runtime Code > Vision > Raw BGR Path

- [ ] Page: `docs/site/runtime-code/vision/raw-bgr-path.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Raw BGR Path.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 199. Runtime Code > Vision > CLAHE Path

- [ ] Page: `docs/site/runtime-code/vision/clahe-path.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: CLAHE Path.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 200. Runtime Code > Vision > Output Scale

- [ ] Page: `docs/site/runtime-code/vision/output-scale.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Output Scale.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 201. Runtime Code > Vision > Model Switching

- [ ] Page: `docs/site/runtime-code/vision/model-switching.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/rc_car_app/vision.py`, `code/ai_models/`
- [ ] TODO checklist:
  - [ ] Explain the camera-steering topic: Model Switching.
  - [ ] Name exact runtime owner functions/files in vision.py.
  - [ ] Document frame format, size, preprocessing, tensor shape, and output units.
  - [ ] Call out Series 1, v2.0/v2.0b, and v2.1+ differences where relevant.
  - [ ] Add one bench test or model steering test command.
  - [ ] Add one field failure this page helps explain.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 202. Runtime Code > Dashboard > Sender

- [ ] Page: `docs/site/runtime-code/dashboard/sender.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/z2w_dashboard.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Sender.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 203. Runtime Code > Dashboard > Receiver

- [ ] Page: `docs/site/runtime-code/dashboard/receiver.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/z2w_dashboard.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Receiver.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 204. Runtime Code > Dashboard > Payload Format

- [ ] Page: `docs/site/runtime-code/dashboard/payload-format.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/z2w_dashboard.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Payload Format.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 205. Runtime Code > Dashboard > Pages

- [ ] Page: `docs/site/runtime-code/dashboard/pages.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/z2w_dashboard.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Pages.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 206. Runtime Code > Dashboard > Idle Exit

- [ ] Page: `docs/site/runtime-code/dashboard/idle-exit.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`, `code/controller/current/z2w_dashboard.py`
- [ ] TODO checklist:
  - [ ] Define the runtime topic: Idle Exit.
  - [ ] List exact owner files/functions and important constants.
  - [ ] Show inputs, outputs, timing, state updates, and side effects.
  - [ ] Explain where manual override, LiDAR, camera model, dashboard, and GPS fit.
  - [ ] Add one debug log or telemetry field to verify behavior.
  - [ ] Add one failure mode and how the runtime handles it.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

## Phase 5 - Hardware, Operations, And Runbooks

Make the physical build and operating workflow reproducible.

- [ ] Phase started
- [ ] Phase drafted
- [ ] Phase reviewed in local MkDocs server

### 207. Hardware > Build Overview

- [ ] Page: `docs/site/hardware/build-overview.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Build Overview.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 208. Hardware > Chassis

- [ ] Page: `docs/site/hardware/chassis.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Chassis.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 209. Hardware > Power

- [ ] Page: `docs/site/hardware/power.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Power.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 210. Hardware > Compute

- [ ] Page: `docs/site/hardware/compute.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Compute.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 211. Hardware > Steering Servo

- [ ] Page: `docs/site/hardware/steering-servo.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Steering Servo.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 212. Hardware > Motors

- [ ] Page: `docs/site/hardware/motors.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Motors.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 213. Hardware > Camera

- [ ] Page: `docs/site/hardware/camera.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Camera.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 214. Hardware > LiDAR

- [ ] Page: `docs/site/hardware/lidar.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/lidar.py`, `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: LiDAR.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 215. Hardware > GPS Compass

- [ ] Page: `docs/site/hardware/gps-compass.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`, `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: GPS Compass.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 216. Hardware > Dashboard Display

- [ ] Page: `docs/site/hardware/dashboard-display.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/z2w_dashboard.py`, `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Dashboard Display.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 217. Hardware > Wiring > Power Wiring

- [ ] Page: `docs/site/hardware/wiring/power-wiring.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Power Wiring.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 218. Hardware > Wiring > Signal Wiring

- [ ] Page: `docs/site/hardware/wiring/signal-wiring.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Signal Wiring.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 219. Hardware > Wiring > I2C

- [ ] Page: `docs/site/hardware/wiring/i2c.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: I2C.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 220. Hardware > Wiring > UART

- [ ] Page: `docs/site/hardware/wiring/uart.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: UART.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 221. Hardware > Wiring > USB

- [ ] Page: `docs/site/hardware/wiring/usb.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: USB.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 222. Operations > Environment Setup

- [ ] Page: `docs/site/operations/environment-setup.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Environment Setup.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 223. Operations > Mac PC Sync

- [ ] Page: `docs/site/operations/mac-pc-sync.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Mac PC Sync.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 224. Operations > NVIDIA PC

- [ ] Page: `docs/site/operations/nvidia-pc.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for NVIDIA PC.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 225. Operations > Raspberry Pi

- [ ] Page: `docs/site/operations/raspberry-pi.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Raspberry Pi.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 226. Operations > Zero 2 W Dashboard

- [ ] Page: `docs/site/operations/zero-2w-dashboard.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/z2w_dashboard.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Zero 2 W Dashboard.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 227. Operations > Command Cookbook

- [ ] Page: `docs/site/operations/command-cookbook.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Command Cookbook.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 228. Operations > Troubleshooting

- [ ] Page: `docs/site/operations/troubleshooting.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Troubleshooting.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 229. Runbooks > Field Test Day > Before Leaving

- [ ] Page: `docs/site/runbooks/field-test-day/before-leaving.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Before Leaving.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 230. Runbooks > Field Test Day > Battery Check

- [ ] Page: `docs/site/runbooks/field-test-day/battery-check.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Battery Check.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 231. Runbooks > Field Test Day > Sensor Check

- [ ] Page: `docs/site/runbooks/field-test-day/sensor-check.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Sensor Check.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 232. Runbooks > Field Test Day > Model Selection

- [ ] Page: `docs/site/runbooks/field-test-day/model-selection.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Model Selection.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 233. Runbooks > Field Test Day > Start Procedure

- [ ] Page: `docs/site/runbooks/field-test-day/start-procedure.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Start Procedure.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 234. Runbooks > Field Test Day > Stop Procedure

- [ ] Page: `docs/site/runbooks/field-test-day/stop-procedure.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Stop Procedure.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 235. Runbooks > Field Test Day > After Run Notes

- [ ] Page: `docs/site/runbooks/field-test-day/after-run-notes.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for After Run Notes.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 236. Runbooks > Training Day > Before Training

- [ ] Page: `docs/site/runbooks/training-day/before-training.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Before Training.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 237. Runbooks > Training Day > Data Audit

- [ ] Page: `docs/site/runbooks/training-day/data-audit.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Data Audit.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 238. Runbooks > Training Day > Command Setup

- [ ] Page: `docs/site/runbooks/training-day/command-setup.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Command Setup.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 239. Runbooks > Training Day > During Training

- [ ] Page: `docs/site/runbooks/training-day/during-training.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for During Training.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 240. Runbooks > Training Day > After Training

- [ ] Page: `docs/site/runbooks/training-day/after-training.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for After Training.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 241. Runbooks > Training Day > Model Export

- [ ] Page: `docs/site/runbooks/training-day/model-export.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`, `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Model Export.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 242. Runbooks > Sync Day > Mac To PC

- [ ] Page: `docs/site/runbooks/sync-day/mac-to-pc.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Mac To PC.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 243. Runbooks > Sync Day > PC To Mac

- [ ] Page: `docs/site/runbooks/sync-day/pc-to-mac.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for PC To Mac.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 244. Runbooks > Sync Day > Delete Risk

- [ ] Page: `docs/site/runbooks/sync-day/delete-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Delete Risk.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 245. Runbooks > Sync Day > Sync Verification

- [ ] Page: `docs/site/runbooks/sync-day/sync-verification.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Write the step-by-step procedure for Sync Verification.
  - [ ] Include exact commands for Mac, NVIDIA PC, or Raspberry Pi as applicable.
  - [ ] Mark destructive commands and sync --delete risk clearly.
  - [ ] Add pre-checks and success checks.
  - [ ] Add rollback/recovery step if something fails.
  - [ ] Keep it usable in the field without rereading theory pages.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

## Phase 6 - Math, Code Reference, Exhibits, Publishing, Roadmap

Add deep technical support material, diagrams, tables, publishing notes, and future work.

- [ ] Phase started
- [ ] Phase drafted
- [ ] Phase reviewed in local MkDocs server

### 246. Research And Math > Geometry > Haversine Distance

- [ ] Page: `docs/site/research-and-math/geometry/haversine-distance.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Haversine Distance.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 247. Research And Math > Geometry > Bearing

- [ ] Page: `docs/site/research-and-math/geometry/bearing.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Bearing.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 248. Research And Math > Geometry > Turn Angle

- [ ] Page: `docs/site/research-and-math/geometry/turn-angle.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Turn Angle.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 249. Research And Math > Geometry > LiDAR Polar Coordinates

- [ ] Page: `docs/site/research-and-math/geometry/lidar-polar-coordinates.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/lidar.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Explain the LiDAR/safety topic: LiDAR Polar Coordinates.
  - [ ] Name exact owner files and constants in lidar.py/runtime.py.
  - [ ] Document packet/scan input, obstacle region output, and stale/fault behavior.
  - [ ] Explain priority over neural-network steering.
  - [ ] Add one disconnect/reconnect or hard-brake test method.
  - [ ] Add one limitation: LiDAR sees obstacles, not sidewalk intent.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 250. Research And Math > Geometry > Camera Resize Geometry

- [ ] Page: `docs/site/research-and-math/geometry/camera-resize-geometry.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Camera Resize Geometry.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 251. Research And Math > Algorithms > A Star Search

- [ ] Page: `docs/site/research-and-math/algorithms/a-star-search.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: A Star Search.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 252. Research And Math > Algorithms > Turn Penalty State

- [ ] Page: `docs/site/research-and-math/algorithms/turn-penalty-state.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Turn Penalty State.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 253. Research And Math > Algorithms > Weighted Sampling

- [ ] Page: `docs/site/research-and-math/algorithms/weighted-sampling.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Weighted Sampling.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 254. Research And Math > Algorithms > PID Cruise Control

- [ ] Page: `docs/site/research-and-math/algorithms/pid-cruise-control.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: PID Cruise Control.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 255. Research And Math > Algorithms > Speed From Hall Pulses

- [ ] Page: `docs/site/research-and-math/algorithms/speed-from-hall-pulses.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Explain the math concept: Speed From Hall Pulses.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 256. Research And Math > Machine Learning > Regression Framing

- [ ] Page: `docs/site/research-and-math/machine-learning/regression-framing.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Regression Framing.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 257. Research And Math > Machine Learning > Loss Function

- [ ] Page: `docs/site/research-and-math/machine-learning/loss-function.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Loss Function.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 258. Research And Math > Machine Learning > Validation Split

- [ ] Page: `docs/site/research-and-math/machine-learning/validation-split.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Validation Split.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 259. Research And Math > Machine Learning > Overfitting Risk

- [ ] Page: `docs/site/research-and-math/machine-learning/overfitting-risk.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Overfitting Risk.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 260. Research And Math > Machine Learning > Sim To Real Gap

- [ ] Page: `docs/site/research-and-math/machine-learning/sim-to-real-gap.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Explain the math concept: Sim To Real Gap.
  - [ ] Give the formula or algorithm in simple terms.
  - [ ] Show where the code implements it.
  - [ ] Add one numeric example using a realistic RC car value.
  - [ ] Explain how a wrong value affects steering, route planning, or safety.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 261. Publishing > Reports

- [ ] Page: `docs/site/publishing/reports.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `mkdocs.yml`, `docs/steering_model_report.pdf`, `docs/huggingface_sidewalkpilot_v*_README.md`
- [ ] TODO checklist:
  - [ ] Document the publishing workflow for Reports.
  - [ ] List generated artifacts and source-of-truth files.
  - [ ] Add exact commands for build, preview, upload, or verification.
  - [ ] Record rules: no stale metrics, no private quiz notes, no future-only claims.
  - [ ] Add a final review checklist for links, files, and public wording.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 262. Publishing > PDF Report

- [ ] Page: `docs/site/publishing/pdf-report.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `mkdocs.yml`, `docs/steering_model_report.pdf`, `docs/huggingface_sidewalkpilot_v*_README.md`
- [ ] TODO checklist:
  - [ ] Document the publishing workflow for PDF Report.
  - [ ] List generated artifacts and source-of-truth files.
  - [ ] Add exact commands for build, preview, upload, or verification.
  - [ ] Record rules: no stale metrics, no private quiz notes, no future-only claims.
  - [ ] Add a final review checklist for links, files, and public wording.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 263. Publishing > Hugging Face Model Cards

- [ ] Page: `docs/site/publishing/huggingface-model-cards.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `mkdocs.yml`, `docs/steering_model_report.pdf`, `docs/huggingface_sidewalkpilot_v*_README.md`
- [ ] TODO checklist:
  - [ ] Document the publishing workflow for Hugging Face Model Cards.
  - [ ] List generated artifacts and source-of-truth files.
  - [ ] Add exact commands for build, preview, upload, or verification.
  - [ ] Record rules: no stale metrics, no private quiz notes, no future-only claims.
  - [ ] Add a final review checklist for links, files, and public wording.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 264. Publishing > MkDocs Site

- [ ] Page: `docs/site/publishing/mkdocs-site.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `mkdocs.yml`, `docs/steering_model_report.pdf`, `docs/huggingface_sidewalkpilot_v*_README.md`
- [ ] TODO checklist:
  - [ ] Document the publishing workflow for MkDocs Site.
  - [ ] List generated artifacts and source-of-truth files.
  - [ ] Add exact commands for build, preview, upload, or verification.
  - [ ] Record rules: no stale metrics, no private quiz notes, no future-only claims.
  - [ ] Add a final review checklist for links, files, and public wording.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 265. Exhibits > Media > Video Index

- [ ] Page: `docs/site/exhibits/media/video-index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Video Index: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 266. Exhibits > Media > Photo Index

- [ ] Page: `docs/site/exhibits/media/photo-index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Photo Index: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 267. Exhibits > Media > Failure Clips

- [ ] Page: `docs/site/exhibits/media/failure-clips.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Failure Clips: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 268. Exhibits > Media > Success Clips

- [ ] Page: `docs/site/exhibits/media/success-clips.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Success Clips: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 269. Exhibits > Media > Dashboard Screenshots

- [ ] Page: `docs/site/exhibits/media/dashboard-screenshots.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/z2w_dashboard.py`, `code/controller/current/rc_car_app/runtime.py`
- [ ] TODO checklist:
  - [ ] Name the demo artifact for Dashboard Screenshots: video, GIF, photo set, or screenshot.
  - [ ] Record date, model version, location/route, lighting, and weather.
  - [ ] Write what the viewer should notice without overselling the result.
  - [ ] Link related field log, failure page, or safety page.
  - [ ] Add filename/path placeholders for media assets to insert later.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 270. Exhibits > Diagrams > System Diagram

- [ ] Page: `docs/site/exhibits/diagrams/system-diagram.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for System Diagram.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 271. Exhibits > Diagrams > Runtime Flow Diagram

- [ ] Page: `docs/site/exhibits/diagrams/runtime-flow-diagram.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Runtime Flow Diagram.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 272. Exhibits > Diagrams > Training Flow Diagram

- [ ] Page: `docs/site/exhibits/diagrams/training-flow-diagram.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Training Flow Diagram.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 273. Exhibits > Diagrams > Safety Arbitration Diagram

- [ ] Page: `docs/site/exhibits/diagrams/safety-arbitration-diagram.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Safety Arbitration Diagram.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 274. Exhibits > Diagrams > Navigation Graph Diagram

- [ ] Page: `docs/site/exhibits/diagrams/navigation-graph-diagram.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/navigation.py`, `code/test_files/astar_nav.py`, `code/test_files/geojson_to_graph.py`
- [ ] TODO checklist:
  - [ ] Explain the navigation topic: Navigation Graph Diagram.
  - [ ] Name the exact graph/node/edge files or navigation.py functions involved.
  - [ ] Document inputs: GPS fix, graph nodes, destination, current route state.
  - [ ] Document outputs: route path, segment mode, handoff alert, resume readiness.
  - [ ] Add one CLI/smoke-test command or graph verification step.
  - [ ] Explain what happens at crosswalks or ambiguous edges if relevant.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 275. Exhibits > Tables > Model Metrics Table

- [ ] Page: `docs/site/exhibits/tables/model-metrics-table.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Model Metrics Table.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 276. Exhibits > Tables > Dataset Table

- [ ] Page: `docs/site/exhibits/tables/dataset-table.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Dataset Table.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 277. Exhibits > Tables > Failure Table

- [ ] Page: `docs/site/exhibits/tables/failure-table.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Failure Table.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 278. Exhibits > Tables > Hardware BOM Table

- [ ] Page: `docs/site/exhibits/tables/hardware-bom-table.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/hardware.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] Document the hardware subsystem: Hardware BOM Table.
  - [ ] List part name, wiring, voltage/current assumptions, and physical mounting notes.
  - [ ] Link exact config constants, pins, channels, or serial ports.
  - [ ] Add setup/calibration steps and one test command.
  - [ ] Add failure symptoms and field fixes.
  - [ ] Add photo/diagram placeholder.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 279. Exhibits > Tables > Test Matrix Table

- [ ] Page: `docs/site/exhibits/tables/test-matrix-table.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] Create or link the exhibit for Test Matrix Table.
  - [ ] Add asset path, date, source, and what the viewer should learn.
  - [ ] Link the exhibit to the relevant narrative, safety, data, or model page.
  - [ ] Add alt text/caption placeholders.
  - [ ] Verify the asset renders in MkDocs before marking done.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 280. Code Reference > File Index

- [ ] Page: `docs/site/code-reference/file-index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to File Index.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 281. Code Reference > Flags Index

- [ ] Page: `docs/site/code-reference/flags-index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to Flags Index.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 282. Code Reference > Functions Index

- [ ] Page: `docs/site/code-reference/functions-index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to Functions Index.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 283. Code Reference > Variables Index

- [ ] Page: `docs/site/code-reference/variables-index.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to Variables Index.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 284. Code Reference > Runtime Modules

- [ ] Page: `docs/site/code-reference/runtime-modules.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/controller/current/rc_car_app/runtime.py`, `code/controller/current/rc_car_app/config.py`
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to Runtime Modules.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 285. Code Reference > Training Modules

- [ ] Page: `docs/site/code-reference/training-modules.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to Training Modules.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 286. Code Reference > Test Files

- [ ] Page: `docs/site/code-reference/test-files.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/test_files/`
- [ ] TODO checklist:
  - [ ] List the files/functions/variables related to Test Files.
  - [ ] For each item, record owner file, inputs, outputs, side effects, and failure modes.
  - [ ] Include command-line flags and defaults when the file is executable.
  - [ ] Mark runtime, training, test, docs, data, or generated-output ownership.
  - [ ] Add links back to the narrative pages that explain why it matters.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 287. Roadmap > Next Steps

- [ ] Page: `docs/site/roadmap/next-steps.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the future work item: Next Steps.
  - [ ] Separate completed facts from proposed next steps.
  - [ ] List the blocker, required data/hardware/code, and test needed to call it done.
  - [ ] Connect it to current failures or limitations.
  - [ ] Keep it public-facing and technically honest.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 288. Roadmap > D0328 Relabel

- [ ] Page: `docs/site/roadmap/d0328-relabel.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the future work item: D0328 Relabel.
  - [ ] Separate completed facts from proposed next steps.
  - [ ] List the blocker, required data/hardware/code, and test needed to call it done.
  - [ ] Connect it to current failures or limitations.
  - [ ] Keep it public-facing and technically honest.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 289. Roadmap > D0329 Relabel

- [ ] Page: `docs/site/roadmap/d0329-relabel.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the future work item: D0329 Relabel.
  - [ ] Separate completed facts from proposed next steps.
  - [ ] List the blocker, required data/hardware/code, and test needed to call it done.
  - [ ] Connect it to current failures or limitations.
  - [ ] Keep it public-facing and technically honest.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 290. Roadmap > Retraining

- [ ] Page: `docs/site/roadmap/retraining.md`
- [ ] File exists: yes
- [ ] Source files to inspect: `code/ai_models_data/train_autonomy_v2.py`, `code/ai_models_data/steering_corrections.json`, `docs/steering_eval_current_labels.json`, `docs/steering_model_report.pdf`
- [ ] TODO checklist:
  - [ ] Define the future work item: Retraining.
  - [ ] Separate completed facts from proposed next steps.
  - [ ] List the blocker, required data/hardware/code, and test needed to call it done.
  - [ ] Connect it to current failures or limitations.
  - [ ] Keep it public-facing and technically honest.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 291. Roadmap > Sensor Fusion

- [ ] Page: `docs/site/roadmap/sensor-fusion.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the future work item: Sensor Fusion.
  - [ ] Separate completed facts from proposed next steps.
  - [ ] List the blocker, required data/hardware/code, and test needed to call it done.
  - [ ] Connect it to current failures or limitations.
  - [ ] Keep it public-facing and technically honest.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

### 292. Roadmap > Reproducibility

- [ ] Page: `docs/site/roadmap/reproducibility.md`
- [ ] File exists: yes
- [ ] Source files to inspect: add exact project files, media, tests, or notes
- [ ] TODO checklist:
  - [ ] Define the future work item: Reproducibility.
  - [ ] Separate completed facts from proposed next steps.
  - [ ] List the blocker, required data/hardware/code, and test needed to call it done.
  - [ ] Connect it to current failures or limitations.
  - [ ] Keep it public-facing and technically honest.
- [ ] Page has links to deeper pages or evidence pages.
- [ ] Page has no stale TODO text after final pass.

## Final Site Review

- [ ] Every nav page exists under docs/site.
- [ ] No public page contains private quiz/prep notes.
- [ ] Every model metric matches docs/steering_eval_current_labels.json or is marked historical.
- [ ] D0328 and D0329 are called First Dataset relabel sources.
- [ ] Field failures are described honestly and linked to the dataset/model iteration they caused.
- [ ] Safety pages clearly say this is a research RC platform, not a public-road autonomous vehicle.
- [ ] Commands are copy-pasteable and identify Mac, NVIDIA PC, or Raspberry Pi context.
- [ ] Videos/images/diagrams have captions and file paths.
- [ ] Run `mkdocs serve` and click every top-level section.
- [ ] Run `mkdocs build --strict` before publishing.
