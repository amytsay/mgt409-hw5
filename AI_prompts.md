# AI Prompts Log — Homework 5

## Problem 1: Vibe coder prompts

**Prompt 1:**

> Okay we are about to start Homework 5, you know the drill set up the Homework 5 folder similar to HW 4 and we will be working in this chat

**Prompt 2 (data and model setup):**

> Okay I downloaded data.zip, please unzip so that data/campus_customs.db acts as the shop database, and then also make a copy of the database file called data/campus_customs_new.dp and make sure the MCP server and backend use that as the working copy. For the shop itself, the field desk.date_today is "today" for the shop. Use this date to determine what is overdue. Please note the other rules of the shop as listed in Hw5. Thank you. Also make sure to use my PORTKEY_API_KEY for AI calls and use gpt-6-luna through portkey for every agent. ONLY use that model as the agent for for AI calls. Since you've set up problem 1 AI_prompts.md, please confirm that problem 1 is complete and we can move to problem 2

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 2: Study the Campus Customs database

**Prompt 1:**

> Okay moving on to Problem 2. Open data/campus_customs.db and make sure to look through every table and its fields, I believe you have already copied the original file to data/campus_customs_new.db, please confirm. Also make sure to study the three open tickets in order to see how they link to other tables (feel free to provide me a summary about what you see). Also be sure to start an output/harness.md. For each table make sure to list the fields and one short line on why that table matters for the agents.

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 3: Build the MCP server

**Prompt 1:**

> Great time to do problem 3. Please write an MCP server in mcp_server/ using FastMCP. Make sure this server is able to talk to data/campus_customs_new.dp. Also all of the agents will use the tools in this MCP server. Alright so right now for the tickets that are open I need at least three tools. Thoughts on potential starter tools? (I'm thinking tools such as accounting tool that will integrate accounts payables, etc and cause a manual approval for release of funds and a flag when cash is low, an inventory and order fulfillment routing tool, to note ordering for items when stock is low) Please come up with and write three of these tools that will be needed for the tickets in the database. Make sure you never invent any of the data and are only using the information in the database. Also make sure to list in the output/harness.md the 3 tools. For each tool that is included make sure it also lists the table it reads, which ticket it helps unlock, and one sentence on why that tool is the right one for that ticket. I need the most points (ideally 100) for this homework so make sure that there is specificity that tie the tool to the ticket. Also make sure to add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has. Perform final checks when complete and let me know if we can move on

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 4: Add the MCP server to your vibe coder and test each tool

**Prompt 1:**

> Okay for problem 4, time to add the MCP server to this project so the vibe coder can call the tools. Make sure to save the connection JSON text in .mcp.json at the project root. Once you are connected, I will look to run and test the tools

**Prompt 2 (Panel B: test each tool):**

> Okay to test the tools, I would like you to 1. check the stock for a random order 2. prepare a payment to an external vendor of $100 3. bulk order 10 hoodies. (Feel free to adjust these tests so that they're smooth and match the tools we created). Make sure for every tool to include the prompt asked, the tool name, and the tool output which must match values in data/campuscustoms_new.db

**Follow-up prompt:** None needed. The first prompt covered everything for this problem. (The later "approved / reopened" messages were app troubleshooting to get the chat to load the new MCP server, not changes to the task.)

## Problem 5: Build the agent team and grow the MCP tools

**Prompt 1:**

> Okay yes now we're on to problem 5, we are looking to now build the agentic tam. This will include a Boss, Inventory, Accounting, Facilities, and Customer Service. Make sure that the team members can work together and delegate work. The boss approves any piece outside the limits and monitors all activities. Inventory reviews and audits stock and reports back to the boss, Accounting works with inventory to check how much order is needed and if it will stay within budget and on hand cash, with the boss overseeing. Facilities works with accounting to make sure rent is paid, but also facilitates payment of the rent and customer service works with inventory and accounting in order to provide accurate timing and fulfillment information to the customer. Please edit and adjust as needed. Make sure the agent prompts are added in backend/prompts/ with one file per agent. Data types go in backend/models.py and agent files are under backend/. Make sure to use PORTKEY_API_KEY and only gpt-6-luna for every agent. Also for rules, make sure to add supporting details to each of the prompts to cover the agent's work, feel free to give me ideas and tips to supplement so that I can score more points. Additionally for the open tickets, feel free to add any additional tools. All shop facts come from the MCP server over data/campus_customs_new.db and no second shop-tools bypass MCP. The agents must also append to output/audit_trail.json as they run. Make sure that the file records so that if an audit is needed later, we can refer to this. Make sure to append and never wipe after a run.
>
> Finally in output/harness.md make sure you list each agent created and each MCP tool created along with which table the tool uses. Also for safety, make sure we keep all client information private, never share and mask all payment data, and make sure we set limits on loops so that agents cannot run indefinitely. Please also add any additional safety guardrails that you feel are important.
>
> Also update mcp_server/README.md so the tool list matches the final updated tool list.

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 6: Plan the three tickets

**Prompt 1:**

> Great I'm good with this. Onto Problem 6. Now we'll write down what we expect the team to do on each open ticket. Which is similar to what we did in the previous problem. So the Boss reviewing ticket 102, then going to facilities and then accounting to route the ticket, facilities to check against the lease and route that number to accounting who then process payments for approval. Add the writing for the remaining problems similarly as well. Make sure to build this into output/desk)_tickets.html which you can double-click with one tab per ticket (101, 102, 1nd 103) Also make sure to add empty cash and reflection tabs for later problems.
>
> On each ticket tab fill an expected section,a nd leave room for an actual section.
>
> Within each ticket's expected section:
>
> please see the below:
> Ticket 101- Boss calls inventory to check stock amounts because this is a problem specificially related to stock
> Inventory then reaches out to Accounting because it requires a reorder, routes the answer back to boss who then alerts customer service this should use the tools, list_tickets, get_ticket, set_ticket_status, check_stock_for_order, get_inventory_report, prepare_restock_order, get_cash_position, prepare_payment, and quote_bulk_order (please let me know if anything is out of the ordinary for these.)
>
> Similarly for Ticket 102- Boss calls facilities in order to assess the rent payment and confirm that it is correct against the lease and then facilities calls accounting to prepare the invoice and payment
> Tools should be list_tickets, get_ticket, set_ticket_status,  get_cash_position, prepare_payment, and get_lease
>
> Finally for Ticket 103: will be boss who calls inventory to check the status of the orders what is possible etc who then refers to accounting to see what the cash position is and if we're able to bulk order, and this routes back to the boss who then alerts customer service to let the customer know. Tools should be: list_tickets, get_ticket, set_ticket_status, check_stock_for_order, get_inventory_report, prepare_restock_order, get_cash_position, prepare_payment, and quote_bulk_order
>
> Please check me as I think this is accurate, and let me know when we can move on

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 7: Backend routes

**Prompt 1:**

> Okay now we're on problem 7 our react frontend dashboard needs a backend that will be backend/main.py make sure to add routes that are able to return the 3 tickets and whether each ticket is open or resolved, take a ticket ID and run the agent team on that ticket. Return recent agent events (ie what each agent said and tools that were used) so the board can refresh. Approve a payment or purchase after a human clicks approve. Return the current checking balance from cash_accounts and finally reset the database to the original values when I want to try a fresh run.
>
> From the backend/ folder start the server with uvicorn main:app --reload --port 8000
> Make sure that the backend is turned on at the link included so that the frontend dashboard can call those routes and then in output/harness.md list each route in one line

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 8: Dashboard

**Prompt 1:**

> Okay great on to Problem 8. Lets build the frontend dashbord in frontend/ with React + VIte + Typescript. This page needs to call the routes you just built. Make sure the board lists all three tickets, allows a user to pick a ticket and start the agent team on it, show each agent and what they are saying/doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on the ticket. Let a human approve a pay or purchase when asked, show the checking balance which drops after an approved pay.
>
> I need this dashboard to be beautiful, make it almost like a third person racing sim, in honor of the new gta 6 coming out, where you can drive to each ticket, and it'll follow through the pathway as it is finished. Give it a full GTA6 theme (appropriate of course), and have a celebration or party when a ticket is completed. Bonus points to me and to you for creativity. Once complete make sure to tell the front end to take to the backend at the local host link. On the backened allow the Vite page origin so that browser is allowed to call those routes. Then start the board with npm run dev. I will pick tickets and watch my agents. Once complete add to output/design.md with what's chosen for the dashboard look in terms of GTA6 theme, how the agents read differently etc. And why certain creative choices are made and why humans would enjoy using this feel free to loop in hype around the newest GTA and breaking up the monotony of a regular workforce dashboard

**Follow-up prompt:** None needed. The first prompt covered everything for this problem.

## Problem 9: Run and resolve the three tickets

**Prompt 1:**

> Great on to problem 9? For problem 9 please rest the working database data/campus_customs_new.db so we start clean. Make sure to note the starting checking balance. Then make sure to run all three tickets on the board (101, 102, 103) until each is resolved. For any unresolved please feel free to prompt me and I will give a solution. Then open output/desk_tickets.html from Problem 6. On each ticket tab, fill out the Actual section from this run, which agents worked, what was delegated, which tools were used. Keep the expected section as the same
>
> On the Cash tab of the same output/desk_tickets.html itemize the money
> -Starting checking balance (after the reset)
> -For each ticket, how cash changed when that ticket was resolved and why (which pay/purchase), dollar amount)
> -Ending checking balance which must match cash_accounts in the working database.
>
> Save output/resolved_tickets.json for each ticket (id, final status, short outcome, agent contribution, human approvals)
> Output/resolved_board.html page you can double-click with screenshot of your react board for each resolved ticket.
>
> Append real runs to output/audit_trail.json, and finish output/harness.md so it covers all the tables, MCP tools, the five agents, API routes, the dashboard, and safety rules
>
> Important things to note for this problem: 1. Make sure the math checks out!!! I cannot lose points. 2. Confirm and review closeout and ability to move onto the next problem

**Follow-up prompt:** None needed. The first prompt covered everything. All three tickets resolved on the first run. The one decision left to the human was which queued payments to approve: I chose "Approve 501 + rent, leave restock pending" on the approval question.

## Problem 10: Reflection

**Prompt 1:**

> Okay moving on to the reflection portion, please give me a comparison overview of expected vs actual and I will start to write my reflection

**Follow-up prompt:**

> Great. let's start logging reflection in output/desk_tickets.html
>
> 1. Rating the performance of the agents on each ticket, I would say that each agent did well given that total time of calls and tokens were relatively low, all tasks were resolved, and the appropriate prompting to the human approval occurred. In particular for Problem 101, the routing went appropriately, the invoice was raised as urgent as it was overdue, and it prompted the cash lowering. For Problem 102, facilities was appropriately reached, the $2400 rent reached for human approval and was click to raise as we need the facility space, and problem was ultimately resolved. For Problem 103, The money requirements were flagged and the issue was raised due to low cash flow. Next steps would need further adjudication.
> 2. For the actual tickets for 101, there were less tools utilized as the team was already ordering the reprint and it was just waiting for the approval of the invoice therefore the prepare_restock_order, and similar tools were not needed. For 102, everything worked out pretty similarly and then for 103, agents were logged at the same time instead of one after the other, and routed to the same agents multiple times.
> 3. Would one agent with tools be simpler? I don't think so as with this problem agents can route at the same time and double check themselves leading to faster resolutions versus one agent taking one step at a time. On the converse side though the interconnectivity with one agent may be stronger.
> 4. Three new problems Campus Customs may face that this team could solve would be. Payment of printing for advertising and or electricity which could be looped under facilities. Second could be a full inventory audit that would be needed to update the online website, and third could be providing estimates to customers inquiring about purchasing new items.
> 5. Three new problems that this agent could not solve for Campus Customs, is one troubleshooting with the customer to figure out the best solution when items are not in stock, if they want to wait or look for something else. Two would be providing influx of cash accounting from the in person store in combination with the online store. Three would be getting new items and adding and accounting for them within all of the appropriate categories (ie frisbees or something).
>
> Make sure to tie every answer to this app and the three tickets that were ran and use the ticket tabs and cash tab on the same page as evidence. Check that these answers are specific and will likely receive high points
>
> Once these are complete please confirm final move on to problem 11

**What the first prompt lacked:** It only asked for an expected-vs-actual overview, so it had no reflection answers and didn't say where to log them.

## Problem 11: Submit to GitHub

**Prompt 1:**

> Okay let's wrap it up. Before zipping do one final full sweep and check for completeness of the full HW and check for accuracy, completion, and ability to gain full points. From there make sure to map the file layout to exactly the one listed in problem 11 and provide any discrencies. Make sure that the real .env is not pushed to the Github repo and make sure that both database files under data/ the original and working copy are included. Once this is complete, prompt me so that we can push to my public github repository.

**Follow-up prompt:**

> mask the names, also test it with a fresh project .venv

**What the first prompt lacked:** It didn't say whether to mask the client names left in SHOP_RULES.md or to prove the README setup works in a fresh project `.venv` before publishing.
