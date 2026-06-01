# New Vision for the product

After concerting with the team here is the new vision that the product
should aim for, in regards to the already established work.

## 0. Long term vision and general direction

The main idea of the project stays the same: Having a tool that 
accelerate the development of ai agents. The project still focuses on
providing a platform to unify the way of working among several agents
for a single user. What is changing is the way this acceleration is
implemented. Until now, the developer only had to program the agents in
themselves and the platform would auto deploy them and talk to an UI
using the custom UI library that allows to define AI frontends
components with YAML files. This is no longer the case. The product
comes at a later stage now: the developer has to build a server for
streaming his agents that follows the platform's endpoint format.
The focus is therefore on the UI / UX capabilities and not on the
runtime anymore.

## 1. Droping the runtime framework runtime handling

The new vision for the product drops the runtime backend unifying the
different agents framework and focuses on the frontend and UX/UI part.
The idea is to define a list of endpoints the frontend app that is
going to be built will talk to. The developer will have to build its 
own backend according to the specification of endpoints. His endpoints 
however can stream any type of events as they will still be unified in
the front app platform specific backend. To that extend, the event
sytem and adapter classes can be reused to translate the different
streamed elements recieved by the proxy server.

## 2. The platform backend

The frontend app / platform still has to have a backend for
conversation history, with folders for organizing them as well as
secrets but not for handling users. This backend still needs to
work as a proxy to redirect the calls from the frontend app to
the backend pointed by the user (the one the developer built with its
agents runtime). This backend can also carry some more capabilities
like loading specific context, plugins and skills into the agents for
instance. The way secrets are going to be handled stays the same: the
user inputs it in the frontend app, it is saved as encrypted in the
DB and sent to the agents runtime backend when streaming.

## 3. UI Widgets revised

The widget system is going to change too. The goal is to program what
is inside a minimal chrome part in the frontend app. The app will
have a folding side menu and a top bar that are constant over all the
agents. Some widgets are going to be collapsed into the side menu.
The filetree and the conversation history are therefore no more widgets
but elements of the side menu. For more specifications about the pure
UX / UI part see #4. The general behavior of widgets might also have to
change to fit the long term vision.

## 4. UX/UI Prototype Porting

The prototype encapsulating the UX/UI vision for the project as well
as frontend elements references are contained into a design handoff
made with Claude design. It describes a very primal behavior for the
app and should be followed for the implementation of this project.
It also contains a design revamp for the widgets that are kept to
match the esthetic of the app in itself.

## 5. To go further

The long term vision also distinguishes two types of apps serving
the  frontend app. The first is simple text based and chat oriented
agents. In that case a simple configuration with the YAML files are
enough to cover the use case. The second one on the other hand is
far more complex. It is agents that need to output complex
datastructures, visializations and interactive material. For this
type of agent systems, the goal is to allow the agents to output
interactive widgets, constrained by the design and capabilities of
the platform. For this, the agents would be provided a skill or a
plugin to avoid any confusion while producing those custom parts
to display to the frontend.