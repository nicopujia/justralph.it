## Just Ralph it

### Table of contents

* [Problem statement](https://nicolaspujia.com/ralph#problem-statement)  
  * [Existing solutions](https://nicolaspujia.com/ralph#existing-solutions)  
* [The solution:](https://nicolaspujia.com/ralph#the-solution-justralphit) [justralph.it](https://justralph.it)  
  * [The software](https://nicolaspujia.com/ralph#the-software)  
    * [Step 1 \- PRD creation](https://nicolaspujia.com/ralph#step-1-prd-creation)  
      * [Ralph-optimized PRDs](https://nicolaspujia.com/ralph#ralph-optimized-prds)  
      * [Collaboration](https://nicolaspujia.com/ralph#collaboration)  
    * [Step 2 \- Ralph loop](https://nicolaspujia.com/ralph#step-2-ralph-loop)  
      * [Updates](https://nicolaspujia.com/ralph#updates)  
      * [Resources expansion](https://nicolaspujia.com/ralph#resources-expansion)  
      * [Limitations and their solution](https://nicolaspujia.com/ralph#limitations-and-their-solution)  
  * [Philosophy](https://nicolaspujia.com/ralph#philosophy)  
    * [Thesis](https://nicolaspujia.com/ralph#thesis)  
      * [On PRs](https://nicolaspujia.com/ralph#on-prs)  
      * [On other existing solutions](https://nicolaspujia.com/ralph#on-other-existing-solutions)  
      * [On legacy code](https://nicolaspujia.com/ralph#on-legacy-code)  
    * [Ownership](https://nicolaspujia.com/ralph#ownership)  
    * [Why build it](https://nicolaspujia.com/ralph#why-build-it)  
      * [More use cases](https://nicolaspujia.com/ralph#more-use-cases)  
  * [Implementation](https://nicolaspujia.com/ralph#implementation)  
    * [Success criteria](https://nicolaspujia.com/ralph#success-criteria)

### Problem statement[¶](https://nicolaspujia.com/ralph#problem-statement)

We already know how powerful the [Ralph Wiggum technique](https://ghuntley.com/ralph/) is. However, setting everything up you need to get it working properly isn't just tedious, but also [very prone to ambiguities](https://nicolaspujia.com/ralph#on-other-existing-solutions), particularly on the PRD.  
Besides, it takes more time if you want to give it more power; which means running it on a VPS with root access, internet access, and all the necessary API keys (what I call god mode); rather than on a constrained Docker container on your home machine, with you in the loop ready to assist.  
And in the case you set Ralph on god mode, it's boilerplate to set up a notifications system to tell you whenever Ralph is actually blocked and needs your help (e.g., in the need of API keys to act on your behalf).  
Let alone the fact that, with the existing tools, no one beyond a curious group of hackers will use the Ralph technique, despite its power.  
Thus, my pain comes from (a) the realization that we currently lack a properly-built tool to create [specific-enough PRDs for agents](https://nicolaspujia.com/ralph#ralph-optimized-prds), and (b) the tediousness of setting up an [effective environment](https://nicolaspujia.com/ralph#step-2-ralph-loop) for Ralph.

#### Existing solutions[¶](https://nicolaspujia.com/ralph#existing-solutions)

* A trained hacker can, of course, do the whole process by himself/herself, though it'd probably take him many hours to get it working right, which includes the hours required to learn about how to apply technique effectively. Furthermore, the whole [Ralph setup is boilerplate](https://nicolaspujia.com/ralph#step-2-ralph-loop).  
* Vibe-coding tools like [v0](https://v0.app), [Lovable](https://lovable.dev/), [Replit](https://replit.com/), etc. not only are all [too constrained](https://nicolaspujia.com/ralph#success-criteria), but also aren't as powerful as Ralph, as [Geoffrey Huntley](https://ghuntley.com/) and all who came after him [have showed us](https://x.com/GeoffreyHuntley/status/1943528204393955634).  
* Asking [Claude Code](https://claude.com/product/claude-code) (CC) or equivalent agents right away to get this working [just doesn't work](https://nicolaspujia.com/ralph#on-other-existing-solutions).

### The solution: [justralph.it](https://justralph.it)[¶](https://nicolaspujia.com/ralph#the-solution-justralphit)

It could be both a course (similar to what [Matt Pocock](https://x.com/mattpocockuk) is doing with [AIhero](https://aihero.dev)) and a software. Both share the same knowledge on a technique. However, the software is its intuitive automation which doesn't currently exist.

#### The software[¶](https://nicolaspujia.com/ralph#the-software)

Proposed to make the process of using the Ralph Wiggum technique easier and more effective, it consists of two main steps.

##### Step 1 \- PRD creation[¶](https://nicolaspujia.com/ralph#step-1-prd-creation)

An app with a chat interface where you start sharing your initial idea, and the chatbot helps you walk through it by asking lots of questions, acting as an idea extractor of your mind.  
You may even discard the idea after some questions. But if you keep going, the chatbot will make sure to gather all the details, mapping all your ideas to well-defined tasks, needed to create a Ralph-optimized PRD. Or, instead of starting with an idea, you might want to [start with a repo](https://nicolaspujia.com/ralph#on-legacy-code) as the initial input, in order to recreate it and then build upon with Ralph.

###### *Ralph-optimized PRDs[¶](https://nicolaspujia.com/ralph#ralph-optimized-prds)*

A Ralph-optimized PRD is a quite different document compared to its standard form (like what you're reading right now). It means having a sequential list of tasks dependent on each other, where each of them is a testable, atomic unit of work with a very concrete success criteria you/your team has agreed upon. It's similar to a pre-defined Git history that, in the initial state, ignores all the fixes and refactors.

###### *Collaboration[¶](https://nicolaspujia.com/ralph#collaboration)*

On top of that, whether it's a 1 or 20-person team, [everyone should be involved](https://nicolaspujia.com/ralph#on-prs) in the PRD creation process, which implies that this step should support collaboration. For an MVP, collaboration could simply be two people in front of the same computer.

##### Step 2 \- Ralph loop[¶](https://nicolaspujia.com/ralph#step-2-ralph-loop)

Once that's done, including that the chatbot doesn't ask more questions, you can click "Just Ralph it." If you do, the following will happen automatically:

1. You get a VPS in your name with root access  
2. Required stuff gets installed on the VPS home directory  
   1. Coding agent  
   2. PRD  
   3. Skills  
   4. PROMPT.md  
   5. Controller to manage the loop within the app UI  
   6. (TBD what else)  
3. The loop starts

By this point, Ralph is working, and you can observe the progress on the app UI.

###### *Updates[¶](https://nicolaspujia.com/ralph#updates)*

However, and as it's expected to happen, the PRD will probably need updates, so you should be able to update it through the UI. When appending a new item, the same chatbot from the beginning ensures that it's Ralph-optimized.  
Important: you shouldn't modify PRD items; only append items, so Ralph doesn't get confused. You can always add a new item saying to remove or fix anything.

###### *Resources expansion[¶](https://nicolaspujia.com/ralph#resources-expansion)*

In the cases where a VPS isn't enough for a project and it needs more web services, the VPS could become the central place for Ralph on that project, from where it would manage the other services through its god mode. It's worth noting, though, that these cases are actually rarer than current intuitions tell us. We live in a world where cloud services have dominated the standard way of deploying software, but most cases are, conversely, [fine with a single machine](https://news.ycombinator.com/item?id=18255110).

###### *Limitations and their solution[¶](https://nicolaspujia.com/ralph#limitations-and-their-solution)*

So, given all this power, what software couldn't Ralph build? Anything that requires:

* Physical presence  
* Locked services (no API, no CLI, no reachable website, etc)  
* Human identity  
* Human taste

For those things is what the notification system is meant for, managed through the loop controller mentioned above, which is nothing else than a piece of software installed on the VPS that communicates with the client in real time.

#### Philosophy[¶](https://nicolaspujia.com/ralph#philosophy)

If the PRD is shallow, the output is shallow; if the PRD is rigorous, the output is rigorous.

##### Thesis[¶](https://nicolaspujia.com/ralph#thesis)

Any well-crafted enough PRD can get built by Ralph.  
(And no, by "well-crafted enough" [I don't mean the exact same code](https://nicolaspujia.com/ralph#ralph-optimized-prds).)

###### *On PRs[¶](https://nicolaspujia.com/ralph#on-prs)*

To make development process more efficient, the review currently made on PRs should be made on [Ralph-optimized PRD](https://nicolaspujia.com/ralph#ralph-optimized-prds) level, not on code level. That doesn't mean that PRDs shouldn't get technical. In fact, the contrary, as it helps Ralph be less prone to commit security issues.

###### *On other existing solutions[¶](https://nicolaspujia.com/ralph#on-other-existing-solutions)*

I see the opposite of my vision on all these agents: after 1 prompt and maybe a few questions, the agent always starts coding. The current plan modes are made with the intention of getting to write the code as soon as possible. No\! Thoroughly, very thoroughly, clarify intent first. By doing so, you will increase the usability and quality of the software, or perhaps even realize that you actually don't want to build what you had thought about.  
To get more accurate and better ideas, we need to get asked more and better questions.

###### *On legacy code[¶](https://nicolaspujia.com/ralph#on-legacy-code)*

Today, for legacy stuff we've got humans in the loop. But tomorrow, reverse-Ralph may, as you said, create Ralph-ready PRDs and just Ralph its way through to a new, clean state of the code where Ralph can build upon.  
Imagine that the initial input isn't a project idea but a legacy codebase. Same output (a Ralph-ready PRD), just with a different input. And then you can just Ralph it.

##### Ownership[¶](https://nicolaspujia.com/ralph#ownership)

You own the PRD, the code, and the VPS access. You have to bring your own keys, which means you'd have to sign in on at least a few external platforms if you want to build something relatively interesting.  
You also own the risk of whatever could happen by having an agent running in god mode on a VPS. That's why this just can't be for everyone. It's based on the premise of giving such power to an AI agent.  
For that reason, it isn't a tool you should use at someone else's company due to liability concerns.

##### Why build it[¶](https://nicolaspujia.com/ralph#why-build-it)

It's something I want and would use myself. In fact, it'd be great to have it build itself.

###### *More use cases[¶](https://nicolaspujia.com/ralph#more-use-cases)*

* Early-startup founders  
* Indie hackers  
* Freelancers  
* Hobbyists  
* In short: anyone who completely owns the code and accountability of whatever they're building.

And in the future, perhaps, the [entire software industry](https://nicolaspujia.com/ralph#on-legacy-code).

#### Implementation[¶](https://nicolaspujia.com/ralph#implementation)

I should build it using the Ralph technique; that way, I'd learn in the process what a good PRD should look like.

###### *Success criteria[¶](https://nicolaspujia.com/ralph#success-criteria)*

It should be able to replicate itself.  
