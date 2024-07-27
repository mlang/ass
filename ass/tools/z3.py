import asyncio

from typing_extensions import Annotated

from pydantic import Field

import z3  # type: ignore

from ass.oai import function


SMT_LIB = Annotated[str,
    Field(
        description="""An SMT-LIB script.""",
        examples=[""";; Solve SEND + MORE = MONEY
(declare-const S Int)
(declare-const E Int)
(declare-const N Int)
(declare-const D Int)
(declare-const M Int)
(declare-const O Int)
(declare-const R Int)
(declare-const Y Int)

(define-fun digit ((x Int)) Bool (and (>= x 0) (<= x 9)))
(assert (digit S))
(assert (digit E))
(assert (digit N))
(assert (digit D))
(assert (digit M))
(assert (digit O))
(assert (digit R))
(assert (digit Y))

(assert (distinct S E N D M O R Y))

(assert (not (= S 0)))
(assert (not (= M 0)))

(define-fun word4 ((a Int) (b Int) (c Int) (d Int)) Int
  (+ (* 1000 a) (* 100 b) (* 10 c) d))
(define-fun word5 ((a Int) (b Int) (c Int) (d Int) (e Int)) Int
  (+ (* 10000 a) (word4 b c d e)))

(assert (= (+ (word4 S E N D) (word4 M O R E)) (word5 M O N E Y)))"""
        ]
    )
]


@function(help="Offer Z3 to the model.")
async def smt(env, /, *, smtlib: SMT_LIB):
    """Add SMT-LIB format assertions to a Z3 solver
    and return the model as an S-expression.

    There is no need for (check-sat) or (get-model) since both will
    implicitly be called by this function.
    """

    with z3.Solver() as solver:
        await _run_sync(solver.from_string, smtlib)
        await _run_sync(solver.check)
        return solver.model().sexpr()


async def _run_sync(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)
